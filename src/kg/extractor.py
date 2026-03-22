import re
import uuid
from typing import Optional

from src.schemas.types import KGEntity, KGRelation, KnowledgeGraph, DocumentChunk


ENTITY_PATTERNS = {}

RELATION_TYPES = []


class EntityExtractor:
    def extract(self, chunk: DocumentChunk) -> list[KGEntity]:
        pass

    def _deduplicate_entities(self, entities: list[KGEntity]) -> list[KGEntity]:
        pass


class RelationExtractor:
    def __init__(self):
        pass

    def _build_relation_patterns(self) -> dict:
        pass

    def extract(self, chunk: DocumentChunk, entities: list[KGEntity]) -> list[KGRelation]:
        pass

    def _find_matching_entity(
        self, text: str, entities: list[KGEntity]
    ) -> Optional[KGEntity]:
        pass


class KGBuilder:
    def __init__(self):
        pass

    def build(self, document_id: str, chunks: list[DocumentChunk]) -> KnowledgeGraph:
        pass


def extract_kg(document_id: str, chunks: list[DocumentChunk]) -> KnowledgeGraph:
    pass
