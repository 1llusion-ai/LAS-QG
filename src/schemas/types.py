from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PARSED = "parsed"
    CLEANED = "cleaned"
    CHUNKED = "chunked"
    KG_BUILT = "kg_built"
    FAILED = "failed"


class DocumentType(str, Enum):
    TXT = "txt"
    DOCX = "docx"
    PDF = "pdf"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Document(BaseModel):
    id: str
    filename: str
    doc_type: DocumentType
    content: str
    status: DocumentStatus = DocumentStatus.PENDING


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: dict = Field(default_factory=dict)


class Rule(BaseModel):
    id: str
    head: str
    relation: str
    tail: str
    doc_title: Optional[str] = None
    article: Optional[str] = None
    chunk_id: Optional[int] = None
    source_text: Optional[str] = None

    @property
    def label(self) -> str:
        return f"{self.head} {self.relation} {self.tail}"


class RuleKnowledgeGraph(BaseModel):
    document_id: str
    rules: list[Rule] = Field(default_factory=list)


class KnowledgeGraph(BaseModel):
    document_id: str
    entities: list[dict] = Field(default_factory=list)
    relations: list[dict] = Field(default_factory=list)


class QuestionPlan(BaseModel):
    difficulty: DifficultyLevel
    knowledge_point: str
    topic: Optional[str] = None
    entities_to_use: list[str] = Field(default_factory=list)
    relations_to_use: list[str] = Field(default_factory=list)
    context_chunks: list[str] = Field(default_factory=list)


class GeneratedQuestion(BaseModel):
    id: str
    question_text: str
    answer: str
    explanation: str
    difficulty: DifficultyLevel
    knowledge_point: str
    source_entities: list[str] = Field(default_factory=list)
    source_relations: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)


class QuestionEvaluation(BaseModel):
    question_id: str
    quality_score: float = Field(ge=0.0, le=1.0)
    difficulty_consistency: float = Field(ge=0.0, le=1.0)
    is_approved: bool
    feedback: str
    evaluation_details: dict = Field(default_factory=dict)


class QuestionBankItem(BaseModel):
    id: str
    question_text: str
    answer: str
    explanation: str
    difficulty: DifficultyLevel
    knowledge_point: str
    source_document_ids: list[str] = Field(default_factory=list)
    is_active: bool = True
    usage_count: int = 0
