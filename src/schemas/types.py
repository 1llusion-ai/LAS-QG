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


class QuestionStatus(str, Enum):
    GENERATED = "generated"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    REJECTED = "rejected"
    STORED = "stored"
    FAILED = "failed"


class EntityType(str, Enum):
    SUBJECT = "subject"
    OBJECT = "object"
    CONDITION = "condition"


class RuleType(str, Enum):
    MUST = "must"
    MUST_NOT = "must_not"
    SHOULD = "should"
    MAY = "may"
    REQUIRES = "requires"
    PROHIBITS = "prohibits"


class ActionType(str, Enum):
    FLY = "fly"
    LAND = "land"
    ASCEND = "ascend"
    DESCEND = "descend"
    MAINTAIN = "maintain"
    AVOID = "avoid"
    REPORT = "report"
    COORDINATE = "coordinate"
    OPERATE = "operate"
    TRANSMIT = "transmit"


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


class KGEntity(BaseModel):
    id: str
    label: str
    entity_type: str
    description: Optional[str] = None
    source_chunk_id: Optional[str] = None


class KGRelation(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    description: Optional[str] = None
    source_chunk_id: Optional[str] = None


class KnowledgeGraph(BaseModel):
    document_id: str
    entities: list[KGEntity] = Field(default_factory=list)
    relations: list[KGRelation] = Field(default_factory=list)


class RuleEntity(BaseModel):
    id: str
    label: str
    entity_type: EntityType
    source_chunk_id: Optional[str] = None
    article_no: Optional[str] = None


class RuleAction(BaseModel):
    id: str
    label: str
    action_type: ActionType
    source_chunk_id: Optional[str] = None
    article_no: Optional[str] = None


class Rule(BaseModel):
    id: str
    label: str
    head: Optional[str] = None
    relation: Optional[str] = None
    tail: Optional[str] = None
    doc_title: Optional[str] = None
    article: Optional[str] = None
    chunk_id: Optional[int] = None
    source_text: Optional[str] = None
    subjects: list[str] = Field(default_factory=list)
    action: Optional[str] = None
    objects: list[str] = Field(default_factory=list)
    modality: Optional[str] = None
    condition_text: Optional[str] = None
    basis_text: Optional[str] = None
    scope_text: Optional[str] = None
    purpose_text: Optional[str] = None
    evidence_text: Optional[str] = None
    source_chunk_id: Optional[str] = None
    article_no: Optional[str] = None


class RuleEdge(BaseModel):
    id: str
    source_id: Optional[str] = None
    source_type: str
    source_label: Optional[str] = None
    target_id: Optional[str] = None
    target_type: str
    target_label: Optional[str] = None
    edge_type: str
    description: Optional[str] = None
    source_chunk_id: Optional[str] = None
    article_no: Optional[str] = None


class RuleKnowledgeGraph(BaseModel):
    document_id: str
    rules: list[Rule] = Field(default_factory=list)


class QuestionRequest(BaseModel):
    difficulty: DifficultyLevel
    knowledge_point: Optional[str] = None
    topic: Optional[str] = None
    count: int = Field(default=1, ge=1, le=10)


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


class WorkflowState(BaseModel):
    document_id: Optional[str] = None
    document: Optional[Document] = None
    chunks: list[DocumentChunk] = Field(default_factory=list)
    kg: Optional[KnowledgeGraph] = None
    rule_kg: Optional[RuleKnowledgeGraph] = None
    question_request: Optional[QuestionRequest] = None
    question_plan: Optional[QuestionPlan] = None
    generated_question: Optional[GeneratedQuestion] = None
    evaluation: Optional[QuestionEvaluation] = None
    retry_count: int = 0
    error: Optional[str] = None
    status: str = "init"
