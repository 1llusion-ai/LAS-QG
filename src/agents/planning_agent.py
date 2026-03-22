import uuid
from typing import Optional

from src.schemas.types import (
    GeneratedQuestion,
    DifficultyLevel,
)
from src.generation.llm_client import BaseLLM
from src.schemas.types import RuleKnowledgeGraph, DocumentChunk


QUESTION_GENERATION_PROMPT = """你是一个低空安全题库生成专家。请根据以下规则知识图谱生成一道题目。

难度要求：{difficulty}

规则图谱信息：
- 实体数量：{entities_count}
- 行为数量：{actions_count}
- 规则数量：{rules_count}
- 边数量：{edges_count}

实体列表：
{entities_text}

行为列表：
{actions_text}

规则列表：
{rules_text}

上下文（来自文档块）：
{context_text}

请生成一道选择题或判断题，包含：
1. 题目文本
2. 正确答案
3. 详细解释

请严格按照以下JSON格式输出，只输出JSON：
{{
    "question_text": "题目内容",
    "answer": "正确答案",
    "explanation": "详细解释"
}}
"""


class PlanningAgent:
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm

    def run(self, rule_kg: RuleKnowledgeGraph, difficulty: DifficultyLevel) -> dict:
        try:
            entities_text = "\n".join([
                f"- {e.label} ({e.entity_type})" for e in rule_kg.entities[:20]
            ])
            actions_text = "\n".join([
                f"- {a.label} ({a.action_type})" for a in rule_kg.actions[:20]
            ])
            rules_text = "\n".join([
                f"- {r.label} ({r.rule_type})" for r in rule_kg.rules[:20]
            ])

            plan = {
                "difficulty": difficulty.value,
                "entities_count": len(rule_kg.entities),
                "actions_count": len(rule_kg.actions),
                "rules_count": len(rule_kg.rules),
                "edges_count": len(rule_kg.edges),
                "entities_text": entities_text,
                "actions_text": actions_text,
                "rules_text": rules_text,
            }

            return {
                "status": "success",
                "plan": plan,
            }

        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "plan": None,
            }


class GenerationAgent:
    def __init__(self, llm: Optional[BaseLLM] = None, max_retries: int = 2):
        self.llm = llm
        self.max_retries = max_retries

    def run(
        self,
        rule_kg: RuleKnowledgeGraph,
        chunks: list[DocumentChunk],
        difficulty: DifficultyLevel,
        plan: dict,
    ) -> dict:
        for attempt in range(self.max_retries + 1):
            try:
                question = self._generate(rule_kg, chunks, difficulty, plan)
                return {
                    "status": "success",
                    "question": question,
                    "attempt": attempt + 1,
                }
            except Exception as e:
                if attempt >= self.max_retries:
                    fallback = self._fallback_generate(difficulty)
                    return {
                        "status": "fallback",
                        "question": fallback,
                        "error": str(e),
                        "attempt": attempt + 1,
                    }

        return {
            "status": "failed",
            "question": None,
            "error": "最大重试次数",
        }

    def _generate(
        self,
        rule_kg: RuleKnowledgeGraph,
        chunks: list[DocumentChunk],
        difficulty: DifficultyLevel,
        plan: dict,
    ) -> GeneratedQuestion:
        context_text = ""
        if chunks:
            context_text = "\n\n".join([c.content[:300] for c in chunks[:3]])

        entities_text = plan.get("entities_text", "")
        actions_text = plan.get("actions_text", "")
        rules_text = plan.get("rules_text", "")

        prompt = QUESTION_GENERATION_PROMPT.format(
            difficulty=difficulty.value,
            entities_count=len(rule_kg.entities),
            actions_count=len(rule_kg.actions),
            rules_count=len(rule_kg.rules),
            edges_count=len(rule_kg.edges),
            entities_text=entities_text,
            actions_text=actions_text,
            rules_text=rules_text,
            context_text=context_text,
        )

        if self.llm:
            response = self.llm.generate(prompt)
            import json
            data = json.loads(response)
            return GeneratedQuestion(
                id=str(uuid.uuid4()),
                question_text=data.get("question_text", ""),
                answer=data.get("answer", ""),
                explanation=data.get("explanation", ""),
                difficulty=difficulty,
                knowledge_point="低空安全规则",
                source_entities=[e.id for e in rule_kg.entities[:5]],
                source_relations=[],
                source_chunk_ids=[c.id for c in chunks[:3]],
            )

        return self._fallback_generate(difficulty)

    def _fallback_generate(self, difficulty: DifficultyLevel) -> GeneratedQuestion:
        questions = {
            DifficultyLevel.EASY: {
                "question_text": "无人机飞行时，以下哪项是必须遵守的规定？",
                "answer": "保持目视视距",
                "explanation": "根据低空安全规定，无人机飞行时应保持目视视距，确保操控员能够清晰观察飞行状态。",
            },
            DifficultyLevel.MEDIUM: {
                "question_text": "在机场附近飞行时，高度限制是多少？",
                "answer": "120米",
                "explanation": "根据相关规定，在机场净空保护区内，无人机飞行高度不得超过120米。",
            },
            DifficultyLevel.HARD: {
                "question_text": "如果需要在禁飞区执行紧急任务，应该如何操作？",
                "answer": "向相关部门申请临时飞行许可",
                "explanation": "即使在禁飞区，如因紧急情况需要飞行，应立即联系民航局或相关管理部门，申请临时飞行许可后方可执行任务。",
            },
        }

        q = questions.get(difficulty, questions[DifficultyLevel.MEDIUM])
        return GeneratedQuestion(
            id=str(uuid.uuid4()),
            question_text=q["question_text"],
            answer=q["answer"],
            explanation=q["explanation"],
            difficulty=difficulty,
            knowledge_point="低空安全规则",
            source_entities=[],
            source_relations=[],
            source_chunk_ids=[],
        )


def get_planning_agent(llm: Optional[BaseLLM] = None) -> PlanningAgent:
    return PlanningAgent(llm)


def get_generation_agent(llm: Optional[BaseLLM] = None) -> GenerationAgent:
    return GenerationAgent(llm)
