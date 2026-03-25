import json
from typing import Optional, Literal

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.agents.state import QuestionAgentState, AgentStep, create_initial_agent_state
from src.agents.tools import get_all_tools, set_tool_dependencies
from src.agents.prompts import SYSTEM_PROMPT
from src.core.llm import BaseLLM
from src.core.neo4j_client import Neo4jClient


class QuestionAgent:
    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        neo4j_client: Optional[Neo4jClient] = None,
        max_iterations: int = 10,
    ):
        self.llm = llm
        self.neo4j_client = neo4j_client
        self.max_iterations = max_iterations
        self.tools = get_all_tools()
        self.graph = self._build_graph()

    def _build_graph(self):
        def agent_node(state: QuestionAgentState) -> dict:
            messages = state.get("messages", [])
            iteration_count = state.get("iteration_count", 0)

            print(f"\n[Agent] 迭代 {iteration_count + 1}")

            if iteration_count >= state.get("max_iterations", self.max_iterations):
                print(f"[Agent] 达到最大迭代次数")
                return {
                    "current_step": AgentStep.COMPLETE,
                    "error": "达到最大迭代次数"
                }

            if self.llm is None:
                print(f"[Agent] LLM客户端未设置")
                return {
                    "current_step": AgentStep.ERROR,
                    "error": "LLM客户端未设置"
                }

            try:
                llm_with_tools = self.llm.bind_tools(self.tools)

                num_questions = state.get("num_questions", 1)
                difficulty = state.get("difficulty", "medium")
                question_type = state.get("question_type", "choice")

                system_content = SYSTEM_PROMPT.format(
                    num_questions=num_questions,
                    difficulty=difficulty,
                    question_type=question_type
                )
                system_message = SystemMessage(content=system_content)
                full_messages = [system_message] + messages

                print(f"[Agent] 调用 LLM...")
                response = llm_with_tools.invoke(full_messages)
                
                print(f"[Agent] LLM 响应 content: {response.content[:200] if response.content else 'None'}...")
                print(f"[Agent] LLM tool_calls: {response.tool_calls if hasattr(response, 'tool_calls') else 'None'}")

                return {
                    "messages": [response],
                    "iteration_count": iteration_count + 1
                }

            except Exception as e:
                print(f"[Agent] 错误: {str(e)}")
                return {
                    "current_step": AgentStep.ERROR,
                    "error": f"Agent执行错误: {str(e)}"
                }

        def tool_node_wrapper(state: QuestionAgentState) -> dict:
            messages = state.get("messages", [])
            if not messages:
                return {}

            last_message = messages[-1]
            if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
                return {}

            print(f"[Tool] 执行工具: {[tc.get('name') for tc in last_message.tool_calls]}")

            tool_node = ToolNode(self.tools)

            tool_input = {"messages": messages}
            result = tool_node.invoke(tool_input)

            new_messages = result.get("messages", [])
            
            for msg in new_messages:
                if hasattr(msg, 'name'):
                    print(f"[Tool] {msg.name} 结果: {msg.content[:200] if msg.content else 'None'}...")

            tool_updates = self._extract_tool_results(new_messages, state)

            return {
                "messages": new_messages,
                **tool_updates
            }

        def should_continue_after_agent(state: QuestionAgentState) -> Literal["tools", "end"]:
            messages = state.get("messages", [])
            error = state.get("error")

            if error:
                print(f"[Router-Agent] 检测到错误，结束")
                return "end"

            if not messages:
                print(f"[Router-Agent] 没有消息，结束")
                return "end"

            last_message = messages[-1]

            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                print(f"[Router-Agent] 有工具调用，执行工具")
                return "tools"

            print(f"[Router-Agent] 没有工具调用，结束")
            return "end"

        def should_continue_after_tools(state: QuestionAgentState) -> Literal["agent", "end"]:
            error = state.get("error")
            current_step = state.get("current_step")
            questions = state.get("questions", []) or []
            num_questions = state.get("num_questions", 1)

            if error:
                print(f"[Router-Tools] 检测到错误，结束")
                return "end"

            if current_step == AgentStep.COMPLETE or len(questions) >= num_questions:
                print(f"[Router-Tools] 已生成 {len(questions)} 道题目，目标 {num_questions}，完成")
                return "end"

            print(f"[Router-Tools] 已生成 {len(questions)} 道题目，目标 {num_questions}，继续")
            return "agent"

        workflow = StateGraph(QuestionAgentState)

        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node_wrapper)

        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            should_continue_after_agent,
            {
                "tools": "tools",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "tools",
            should_continue_after_tools,
            {
                "agent": "agent",
                "end": END
            }
        )

        return workflow.compile()

    def _extract_tool_results(self, messages: list, state: QuestionAgentState) -> dict:
        updates = {}

        for msg in messages:
            if hasattr(msg, "name") and hasattr(msg, "content"):
                tool_name = msg.name
                content = msg.content

                try:
                    result = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    continue

                if tool_name == "retrieve_chunks":
                    if result.get("status") == "success":
                        updates["chunks"] = result.get("chunks", [])
                        updates["current_step"] = AgentStep.RETRIEVE_CHUNKS

                elif tool_name == "retrieve_subgraph":
                    if result.get("status") == "success":
                        updates["subgraph"] = result.get("subgraph", {})
                        updates["current_step"] = AgentStep.RETRIEVE_SUBGRAPH

                elif tool_name == "generate_questions":
                    if result.get("status") == "success":
                        updates["current_question"] = result.get("question")
                        updates["current_step"] = AgentStep.GENERATE
                        existing_questions = state.get("questions", []) or []
                        new_questions = list(existing_questions)
                        new_questions.append(result.get("question"))
                        updates["questions"] = new_questions
                        print(f"[Tool] 已生成 {len(new_questions)} 道题目")

                elif tool_name == "evaluate_questions":
                    if result.get("status") == "success":
                        updates["evaluation"] = result
                        updates["current_step"] = AgentStep.EVALUATE
                        if result.get("is_approved"):
                            updates["current_step"] = AgentStep.COMPLETE

        return updates

    def run(
        self,
        user_query: str,
        difficulty: str = "medium",
        question_type: str = "choice",
        num_questions: int = 1,
    ) -> dict:
        set_tool_dependencies(neo4j_client=self.neo4j_client, llm_client=self.llm)

        initial_state = create_initial_agent_state(
            user_query=user_query,
            difficulty=difficulty,
            question_type=question_type,
            num_questions=num_questions,
            max_iterations=self.max_iterations
        )

        initial_state["messages"] = [HumanMessage(content=user_query)]

        try:
            result = self.graph.invoke(initial_state)
            return self._format_result(result)
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "questions": [],
                "evaluation": None
            }

    def _format_result(self, state: QuestionAgentState) -> dict:
        questions = state.get("questions", [])
        current_question = state.get("current_question")
        evaluation = state.get("evaluation")
        error = state.get("error")
        current_step = state.get("current_step")

        if current_question and current_question not in questions:
            questions.append(current_question)

        status = "success"
        if error:
            status = "error"
        elif current_step == AgentStep.COMPLETE:
            status = "completed"
        elif current_step == AgentStep.EVALUATE:
            status = "evaluated"

        return {
            "status": status,
            "questions": questions,
            "current_question": current_question,
            "evaluation": evaluation,
            "chunks": state.get("chunks", []),
            "subgraph": state.get("subgraph", {}),
            "error": error,
            "iteration_count": state.get("iteration_count", 0)
        }


def create_question_agent(
    llm: Optional[BaseLLM] = None,
    neo4j_client: Optional[Neo4jClient] = None,
    max_iterations: int = 10,
) -> QuestionAgent:
    return QuestionAgent(
        llm=llm,
        neo4j_client=neo4j_client,
        max_iterations=max_iterations
    )
