import networkx as nx
from typing import Optional

from src.schemas.types import KnowledgeGraph, KGEntity, KGRelation


class KGGraph:
    def __init__(self, kg: KnowledgeGraph):
        pass

    def _build_graph(self, kg: KnowledgeGraph) -> nx.DiGraph:
        pass

    def get_subgraph(
        self, entity_ids: list[str], depth: int = 1
    ) -> nx.DiGraph:
        pass

    def get_connected_entities(self, entity_id: str) -> list[KGEntity]:
        pass

    def find_paths(
        self, source_id: str, target_id: str, max_length: int = 3
    ) -> list[list[str]]:
        pass


def nxego_graph(G: nx.DiGraph, node: str, radius: int) -> nx.DiGraph:
    pass


def build_kg_graph(kg: KnowledgeGraph) -> KGGraph:
    pass


def get_subgraph(kg: KnowledgeGraph, entity_ids: list[str], depth: int = 1) -> nx.DiGraph:
    pass
