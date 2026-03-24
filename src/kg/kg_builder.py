import uuid
from typing import Optional, Any


def _get_attr(obj: Any, key: str, default=None):
    if hasattr(obj, 'get') and callable(getattr(obj, 'get')):
        return obj.get(key, default)
    return getattr(obj, key, default)


class RuleKGBuilder:
    def __init__(self):
        self.graph = None
        self._entity_map = {}
        self._chunk_map = {}

    def build_from_rules(self, rules: list) -> "RuleKGBuilder":
        import networkx as nx

        self.graph = nx.DiGraph()
        self._entity_map = {}
        self._chunk_map = {}

        for rule in rules:
            head = _get_attr(rule, "head", "")
            relation = _get_attr(rule, "relation", "")
            tail = _get_attr(rule, "tail", "")
            doc_title = _get_attr(rule, "doc_title", "")
            article = _get_attr(rule, "article", "")
            source_text = _get_attr(rule, "source_text", "")
            chunk_id = _get_attr(rule, "chunk_id", 0)

            if not head or not relation or not tail:
                continue

            head_id = self._get_or_create_entity(head)
            tail_id = self._get_or_create_entity(tail)

            chunk_key = f"{doc_title}_{chunk_id}"
            chunk_node_id = self._get_or_create_chunk(
                chunk_key=chunk_key,
                chunk_id=chunk_id,
                doc_title=doc_title,
                article=article,
                source_text=source_text
            )

            edge_id = f"edge_{uuid.uuid4().hex[:12]}"
            self.graph.add_edge(
                head_id,
                tail_id,
                id=edge_id,
                edge_type="relation",
                relation=relation,
                doc_title=doc_title,
                article=article,
                source_text=source_text,
                chunk_id=chunk_id,
                chunk_node_id=chunk_node_id,
            )

        return self

    def _get_or_create_entity(self, name: str) -> str:
        if name not in self._entity_map:
            entity_id = f"entity_{uuid.uuid5(uuid.NAMESPACE_DNS, name).hex[:12]}"
            self._entity_map[name] = entity_id
            if self.graph is not None:
                self.graph.add_node(
                    entity_id,
                    node_type="entity",
                    name=name,
                    label=name[:30] + "..." if len(name) > 30 else name
                )
        return self._entity_map[name]

    def _get_or_create_chunk(self, chunk_key: str, chunk_id: int, doc_title: str, article: str, source_text: str) -> str:
        if chunk_key not in self._chunk_map:
            chunk_node_id = f"chunk_{chunk_key}"
            self._chunk_map[chunk_key] = chunk_node_id
            if self.graph is not None:
                self.graph.add_node(
                    chunk_node_id,
                    node_type="chunk",
                    chunk_key=chunk_key,
                    chunk_id=chunk_id,
                    doc_title=doc_title,
                    article=article,
                    source_text=source_text,
                    label=f"Chunk_{chunk_id}"
                )
        return self._chunk_map[chunk_key]

    def get_graph(self):
        return self.graph

    def get_graph_stats(self) -> dict:
        if self.graph is None:
            return {
                "nodes": 0,
                "edges": 0,
                "node_types": {},
                "edge_types": {},
                "relation_types": {},
                "documents": [],
                "entities_count": 0,
                "chunks_count": 0,
            }

        stats = {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": {},
            "edge_types": {},
            "relation_types": {},
            "documents": set(),
            "entities_count": 0,
            "chunks_count": 0,
        }

        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "unknown")
            stats["node_types"][node_type] = stats["node_types"].get(node_type, 0) + 1
            if node_type == "entity":
                stats["entities_count"] += 1
            elif node_type == "chunk":
                stats["chunks_count"] += 1
                stats["documents"].add(data.get("doc_title", ""))

        for u, v, data in self.graph.edges(data=True):
            edge_type = data.get("edge_type", "unknown")
            stats["edge_types"][edge_type] = stats["edge_types"].get(edge_type, 0) + 1

            relation = data.get("relation", "")
            if relation:
                stats["relation_types"][relation] = stats["relation_types"].get(relation, 0) + 1

        stats["documents"] = list(stats["documents"])
        return stats

    def to_cytoscape_json(self) -> dict:
        elements = {"nodes": [], "edges": []}
        if self.graph is None:
            return elements

        node_colors = {
            "entity": "#4ECDC4",
            "chunk": "#FF6B6B",
        }

        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "entity")
            elements["nodes"].append({
                "data": {
                    "id": node,
                    "label": data.get("label", node),
                    "type": node_type,
                    "name": data.get("name", ""),
                    "color": node_colors.get(node_type, "#CCCCCC")
                }
            })

        for u, v, data in self.graph.edges(data=True):
            elements["edges"].append({
                "data": {
                    "id": data.get("id", f"{u}_{v}"),
                    "source": u,
                    "target": v,
                    "relation": data.get("relation", ""),
                    "label": data.get("relation", ""),
                    "article": data.get("article", ""),
                }
            })

        return elements

    def to_neo4j_cypher_data(self) -> list:
        cypher_data = []
        if self.graph is None:
            return cypher_data

        for chunk_key, chunk_node_id in self._chunk_map.items():
            node_data = self.graph.nodes.get(chunk_node_id, {})
            if node_data.get("node_type") == "chunk":
                cypher_data.append({
                    "type": "chunk",
                    "chunk_key": chunk_key,
                    "chunk_id": node_data.get("chunk_id", 0),
                    "doc_title": node_data.get("doc_title", ""),
                    "article": node_data.get("article", ""),
                    "source_text": node_data.get("source_text", ""),
                })

        for entity_name, entity_id in self._entity_map.items():
            cypher_data.append({
                "type": "entity",
                "name": entity_name,
            })

        for u, v, data in self.graph.edges(data=True):
            if data.get("edge_type") == "relation":
                head_name = self.graph.nodes[u].get("name", "")
                tail_name = self.graph.nodes[v].get("name", "")
                cypher_data.append({
                    "type": "relation",
                    "head": head_name,
                    "tail": tail_name,
                    "relation_text": data.get("relation", ""),
                    "doc_title": data.get("doc_title", ""),
                    "article": data.get("article", ""),
                    "chunk_id": data.get("chunk_id", 0),
                })

        return cypher_data


def build_rule_kg(rules: list) -> RuleKGBuilder:
    builder = RuleKGBuilder()
    return builder.build_from_rules(rules)
