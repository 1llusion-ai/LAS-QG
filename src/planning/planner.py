import uuid
from typing import Optional

from src.schemas.types import (
    QuestionRequest,
    QuestionPlan,
    DifficultyLevel,
    KnowledgeGraph,
)
from src.generation.llm_client import BaseLLM


class QuestionPlanner:
    def __init__(self, llm: Optional[BaseLLM] = None):
        pass

    def plan(self, request: QuestionRequest, kg: KnowledgeGraph) -> QuestionPlan:
        pass

    def _llm_plan(self, request: QuestionRequest, kg: KnowledgeGraph) -> QuestionPlan:
        pass

    def _rule_based_plan(
        self, request: QuestionRequest, kg: KnowledgeGraph
    ) -> QuestionPlan:
        pass


def plan_question(request: QuestionRequest, kg: KnowledgeGraph, llm: Optional[BaseLLM] = None) -> QuestionPlan:
    pass
