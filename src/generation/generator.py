import uuid
from typing import Optional

from src.schemas.types import (
    GeneratedQuestion,
    QuestionPlan,
    DifficultyLevel,
    KnowledgeGraph,
    DocumentChunk,
)
from src.generation.llm_client import BaseLLM


class QuestionGenerator:
    def __init__(self, llm: Optional[BaseLLM] = None):
        pass

    def generate(
        self,
        plan: QuestionPlan,
        kg: KnowledgeGraph,
        chunks: list[DocumentChunk],
    ) -> GeneratedQuestion:
        pass

    def _build_context(
        self, plan: QuestionPlan, kg: KnowledgeGraph, chunks: list[DocumentChunk]
    ) -> str:
        pass

    def _llm_generate(self, plan: QuestionPlan, context: str) -> GeneratedQuestion:
        pass

    def _rule_based_generate(
        self, plan: QuestionPlan, context: str
    ) -> GeneratedQuestion:
        pass


def generate_question(
    plan: QuestionPlan,
    kg: KnowledgeGraph,
    chunks: list[DocumentChunk],
    llm: Optional[BaseLLM] = None,
) -> GeneratedQuestion:
    pass
