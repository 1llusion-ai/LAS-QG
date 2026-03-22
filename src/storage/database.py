import sqlite3
import json
from pathlib import Path
from typing import Optional

from src.schemas.types import (
    QuestionBankItem,
    DifficultyLevel,
    Document,
    DocumentChunk,
    KnowledgeGraph,
)


class Database:
    DB_PATH = Path("data/question_bank.db")

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = self.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id TEXT PRIMARY KEY,
                    question_text TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    knowledge_point TEXT NOT NULL,
                    source_document_ids TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    usage_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_graphs (
                    document_id TEXT PRIMARY KEY,
                    entities TEXT NOT NULL,
                    relations TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_questions_difficulty
                ON questions(difficulty)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_questions_knowledge_point
                ON questions(knowledge_point)
            """)


class QuestionBank:
    def __init__(self, db_path: Optional[str] = None):
        self.db = Database(db_path)

    def add_question(self, question: QuestionBankItem) -> bool:
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO questions
                    (id, question_text, answer, explanation, difficulty,
                     knowledge_point, source_document_ids, is_active, usage_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        question.id,
                        question.question_text,
                        question.answer,
                        question.explanation,
                        question.difficulty.value,
                        question.knowledge_point,
                        json.dumps(question.source_document_ids),
                        1 if question.is_active else 0,
                        question.usage_count,
                    ),
                )
                return True
        except sqlite3.IntegrityError:
            return False

    def get_question(self, question_id: str) -> Optional[QuestionBankItem]:
        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM questions WHERE id = ?", (question_id,)
            ).fetchone()

            if row:
                return self._row_to_question(row)
            return None

    def get_questions(
        self,
        difficulty: Optional[DifficultyLevel] = None,
        knowledge_point: Optional[str] = None,
        limit: int = 50,
    ) -> list[QuestionBankItem]:
        query = "SELECT * FROM questions WHERE is_active = 1"
        params = []

        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty.value)

        if knowledge_point:
            query += " AND knowledge_point LIKE ?"
            params.append(f"%{knowledge_point}%")

        query += " ORDER BY usage_count ASC, created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_question(row) for row in rows]

    def check_duplicate(self, question_text: str) -> bool:
        normalized = question_text.lower().strip()
        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id FROM questions
                WHERE LOWER(TRIM(question_text)) = ?
                """,
                (normalized,),
            ).fetchone()
            return row is not None

    def increment_usage(self, question_id: str):
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute(
                "UPDATE questions SET usage_count = usage_count + 1 WHERE id = ?",
                (question_id,),
            )

    def deactivate_question(self, question_id: str) -> bool:
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute(
                "UPDATE questions SET is_active = 0 WHERE id = ?",
                (question_id,),
            )
            return cursor.rowcount > 0

    def _row_to_question(self, row: sqlite3.Row) -> QuestionBankItem:
        return QuestionBankItem(
            id=row["id"],
            question_text=row["question_text"],
            answer=row["answer"],
            explanation=row["explanation"],
            difficulty=DifficultyLevel(row["difficulty"]),
            knowledge_point=row["knowledge_point"],
            source_document_ids=json.loads(row["source_document_ids"]),
            is_active=bool(row["is_active"]),
            usage_count=row["usage_count"],
        )


class DocumentStorage:
    def __init__(self, db_path: Optional[str] = None):
        self.db = Database(db_path)

    def save_document(self, document: Document) -> bool:
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO documents (id, filename, doc_type, content, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        document.id,
                        document.filename,
                        document.doc_type.value,
                        document.content,
                        document.status.value,
                    ),
                )
                return True
        except sqlite3.IntegrityError:
            return False

    def get_document(self, document_id: str) -> Optional[Document]:
        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (document_id,)
            ).fetchone()

            if row:
                return Document(
                    id=row["id"],
                    filename=row["filename"],
                    doc_type=row["doc_type"],
                    content=row["content"],
                    status=row["status"],
                )
            return None

    def save_chunks(self, chunks: list[DocumentChunk]) -> bool:
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                for chunk in chunks:
                    conn.execute(
                        """
                        INSERT INTO chunks (id, document_id, chunk_index, content, metadata)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.id,
                            chunk.document_id,
                            chunk.chunk_index,
                            chunk.content,
                            json.dumps(chunk.metadata),
                        ),
                    )
                return True
        except sqlite3.IntegrityError:
            return False

    def get_chunks(self, document_id: str) -> list[DocumentChunk]:
        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            ).fetchall()

            return [
                DocumentChunk(
                    id=row["id"],
                    document_id=row["document_id"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    metadata=json.loads(row["metadata"]),
                )
                for row in rows
            ]

    def save_kg(self, kg: KnowledgeGraph) -> bool:
        try:
            with sqlite3.connect(self.db.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO knowledge_graphs
                    (document_id, entities, relations)
                    VALUES (?, ?, ?)
                    """,
                    (
                        kg.document_id,
                        json.dumps([e.model_dump() for e in kg.entities]),
                        json.dumps([r.model_dump() for r in kg.relations]),
                    ),
                )
                return True
        except sqlite3.IntegrityError:
            return False

    def get_kg(self, document_id: str) -> Optional[KnowledgeGraph]:
        from src.schemas.types import KGEntity, KGRelation

        with sqlite3.connect(self.db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM knowledge_graphs WHERE document_id = ?",
                (document_id,),
            ).fetchone()

            if row:
                entities_data = json.loads(row["entities"])
                relations_data = json.loads(row["relations"])
                entities = [KGEntity(**e) for e in entities_data]
                relations = [KGRelation(**r) for r in relations_data]
                return KnowledgeGraph(
                    document_id=document_id,
                    entities=entities,
                    relations=relations,
                )
            return None


def get_question_bank(db_path: Optional[str] = None) -> QuestionBank:
    return QuestionBank(db_path)


def get_document_storage(db_path: Optional[str] = None) -> DocumentStorage:
    return DocumentStorage(db_path)
