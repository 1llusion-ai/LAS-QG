from typing import TypedDict, Optional
from enum import Enum

from src.schemas.types import (
    Document,
    DocumentChunk,
    RuleKnowledgeGraph,
    GeneratedQuestion,
    QuestionEvaluation,
    DifficultyLevel,
)


class WorkflowStatus(str, Enum):
    INIT = "init"
    PARSING = "parsing"
    CHUNKING = "chunking"
    KG_EXTRACTING = "kg_extracting"
    PLANNING = "planning"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    COMPLETED = "completed"


class WorkflowState(TypedDict):
    document: Optional[Document]
    chunks: list[DocumentChunk]
    rule_kg: Optional[RuleKnowledgeGraph]
    question_plan: Optional[dict]
    generated_question: Optional[GeneratedQuestion]
    evaluation: Optional[QuestionEvaluation]
    difficulty: Optional[DifficultyLevel]
    status: WorkflowStatus
    error: Optional[str]
    retry_count: int
    chunks_processed: int
    extraction_status: Optional[str]
    generation_status: Optional[str]
    evaluation_status: Optional[str]


def create_initial_state(
    document: Document,
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
) -> WorkflowState:
    return WorkflowState(
        document=document,
        chunks=[],
        rule_kg=None,
        question_plan=None,
        generated_question=None,
        evaluation=None,
        difficulty=difficulty,
        status=WorkflowStatus.INIT,
        error=None,
        retry_count=0,
        chunks_processed=0,
        extraction_status=None,
        generation_status=None,
        evaluation_status=None,
    )
