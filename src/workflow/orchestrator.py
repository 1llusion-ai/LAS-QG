from typing import Optional

from src.workflow.state import WorkflowState, WorkflowStatus
from src.cleaner.text_cleaner import clean_text
from src.cleaner.text_chunker import chunk_document
from src.kg.rule_extractor import extract_rule_kg
from src.generation.llm_client import BaseLLM
from src.agents.planning_agent import PlanningAgent, GenerationAgent
from src.evaluation.evaluator import evaluate_question

from langgraph.graph import StateGraph, END


MAX_RETRIES = 1


def chunking_node(state: WorkflowState) -> WorkflowState:
    try:
        document = state["document"]
        if document is None:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = "没有文档"
            return state

        cleaned_content = clean_text(document.content)
        document.content = cleaned_content

        chunks = chunk_document(document)
        state["chunks"] = chunks
        state["status"] = WorkflowStatus.CHUNKING

        return state

    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["error"] = f"切块失败: {str(e)}"
        return state


def kg_extraction_node(state: WorkflowState) -> WorkflowState:
    try:
        document = state["document"]
        chunks = state.get("chunks", [])

        if document is None or not chunks:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = "没有文档或块"
            return state

        llm = state.get("llm")
        rule_kg = extract_rule_kg(document.id, chunks, llm)

        state["rule_kg"] = rule_kg
        state["status"] = WorkflowStatus.KG_EXTRACTING
        state["extraction_status"] = "success"
        state["chunks_processed"] = len(chunks)

        return state

    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["error"] = f"知识图谱抽取失败: {str(e)}"
        state["extraction_status"] = "failed"
        return state


def planning_node(state: WorkflowState) -> WorkflowState:
    try:
        rule_kg = state.get("rule_kg")
        difficulty = state.get("difficulty")
        llm = state.get("llm")

        if rule_kg is None:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = "没有知识图谱"
            return state

        planner = PlanningAgent(llm)
        result = planner.run(rule_kg, difficulty)

        if result["status"] == "success":
            state["question_plan"] = result["plan"]
            state["status"] = WorkflowStatus.PLANNING
        else:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = f"规划失败: {result.get('error', '未知错误')}"

        return state

    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["error"] = f"规划失败: {str(e)}"
        return state


def generation_node(state: WorkflowState) -> WorkflowState:
    try:
        rule_kg = state.get("rule_kg")
        chunks = state.get("chunks", [])
        difficulty = state.get("difficulty")
        plan = state.get("question_plan")
        llm = state.get("llm")

        if rule_kg is None:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = "没有知识图谱"
            return state

        generator = GenerationAgent(llm)
        result = generator.run(rule_kg, chunks, difficulty, plan)

        if result["status"] in ["success", "fallback"]:
            state["generated_question"] = result["question"]
            state["status"] = WorkflowStatus.GENERATING
            state["generation_status"] = result["status"]
        else:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = f"问题生成失败: {result.get('error', '未知错误')}"
            state["generation_status"] = "failed"

        return state

    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["error"] = f"问题生成失败: {str(e)}"
        state["generation_status"] = "failed"
        return state


def evaluation_node(state: WorkflowState) -> WorkflowState:
    try:
        question = state.get("generated_question")
        llm = state.get("llm")

        if question is None:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = "没有生成的问题"
            return state

        evaluation = evaluate_question(question, llm)

        state["evaluation"] = evaluation
        state["status"] = WorkflowStatus.EVALUATING

        if evaluation.is_approved:
            state["status"] = WorkflowStatus.APPROVED
        else:
            retry_count = state.get("retry_count", 0)
            if retry_count < MAX_RETRIES:
                state["retry_count"] = retry_count + 1
                state["status"] = WorkflowStatus.REJECTED
            else:
                state["status"] = WorkflowStatus.REJECTED

        return state

    except Exception as e:
        state["status"] = WorkflowStatus.FAILED
        state["error"] = f"评估失败: {str(e)}"
        state["evaluation_status"] = "failed"
        return state


def should_retry(state: WorkflowState) -> bool:
    return (
        state.get("status") == WorkflowStatus.REJECTED
        and state.get("retry_count", 0) < MAX_RETRIES
    )


def should_approve(state: WorkflowState) -> bool:
    return state.get("status") == WorkflowStatus.APPROVED


def create_workflow():
    workflow = StateGraph(WorkflowState)

    workflow.add_node("chunking", chunking_node)
    workflow.add_node("kg_extraction", kg_extraction_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("generation", generation_node)
    workflow.add_node("evaluation", evaluation_node)

    workflow.set_entry_point("chunking")
    workflow.add_edge("chunking", "kg_extraction")
    workflow.add_edge("kg_extraction", "planning")
    workflow.add_edge("planning", "generation")
    workflow.add_edge("generation", "evaluation")

    workflow.add_conditional_edges(
        "evaluation",
        lambda s: (
            "retry_generation"
            if should_retry(s)
            else "approved" if should_approve(s) else "rejected"
        ),
        {
            "retry_generation": "generation",
            "approved": END,
            "rejected": END,
        },
    )

    return workflow.compile()


class QuestionGenerationWorkflow:
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm
        self.graph = create_workflow()

    def run(self, state: WorkflowState) -> WorkflowState:
        state["llm"] = self.llm
        result = self.graph.invoke(state)
        return result

    def run_with_fallback(self, state: WorkflowState) -> WorkflowState:
        try:
            return self.run(state)
        except Exception as e:
            state["status"] = WorkflowStatus.FAILED
            state["error"] = str(e)
            return state


def run_workflow(
    document,
    difficulty,
    llm: Optional[BaseLLM] = None,
) -> WorkflowState:
    from src.workflow.state import create_initial_state

    state = create_initial_state(document, difficulty)
    workflow = QuestionGenerationWorkflow(llm)
    return workflow.run_with_fallback(state)
