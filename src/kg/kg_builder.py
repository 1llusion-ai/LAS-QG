from typing import Optional
import networkx as nx


def _get_attr(obj, key, default=None):
    if hasattr(obj, 'get') and callable(getattr(obj, 'get')):
        return obj.get(key, default)
    return getattr(obj, key, default)


class RuleKGBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

    def build_from_rules(self, rules: list) -> nx.DiGraph:
        for rule in rules:
            rule_id = _get_attr(rule, "id", "")
            label = _get_attr(rule, "label", "")

            self.graph.add_node(rule_id, node_type="rule", label=label)

            for subject in _get_attr(rule, "subjects", []):
                if subject:
                    subject_id = f"subject_{subject}"
                    self.graph.add_node(subject_id, node_type="subject", label=subject)
                    self.graph.add_edge(subject_id, rule_id, edge_type="subject_of")

            action = _get_attr(rule, "action")
            if action:
                action_id = f"action_{action}"
                self.graph.add_node(action_id, node_type="action", label=action)
                self.graph.add_edge(rule_id, action_id, edge_type="requires_action")

            for obj in _get_attr(rule, "objects", []):
                if obj:
                    obj_id = f"object_{obj}"
                    self.graph.add_node(obj_id, node_type="object", label=obj)
                    if action:
                        action_id = f"action_{action}"
                        self.graph.add_edge(action_id, obj_id, edge_type="targets")

            modality = _get_attr(rule, "modality")
            if modality:
                modality_id = f"modality_{modality}"
                self.graph.add_node(modality_id, node_type="modality", label=modality)
                self.graph.add_edge(rule_id, modality_id, edge_type="has_modality")

            condition = _get_attr(rule, "condition_text")
            if condition:
                condition_id = f"condition_{hash(condition)}"
                self.graph.add_node(condition_id, node_type="condition", label=condition)
                self.graph.add_edge(rule_id, condition_id, edge_type="when")

            scope = _get_attr(rule, "scope_text")
            if scope:
                scope_id = f"scope_{hash(scope)}"
                self.graph.add_node(scope_id, node_type="scope", label=scope)
                self.graph.add_edge(rule_id, scope_id, edge_type="applies_to")

            purpose = _get_attr(rule, "purpose_text")
            if purpose:
                purpose_id = f"purpose_{hash(purpose)}"
                self.graph.add_node(purpose_id, node_type="purpose", label=purpose)
                self.graph.add_edge(rule_id, purpose_id, edge_type="aims_at")

        return self.graph

    def get_graph_stats(self) -> dict:
        stats = {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": {},
            "edge_types": {}
        }

        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "unknown")
            stats["node_types"][node_type] = stats["node_types"].get(node_type, 0) + 1

        for u, v, data in self.graph.edges(data=True):
            edge_type = data.get("edge_type", "unknown")
            stats["edge_types"][edge_type] = stats["edge_types"].get(edge_type, 0) + 1

        return stats

    def to_cytoscape_json(self) -> dict:
        elements = {"nodes": [], "edges": []}

        node_colors = {
            "rule": "#FF6B6B",
            "subject": "#4ECDC4",
            "action": "#45B7D1",
            "object": "#96CEB4",
            "modality": "#FFEAA7",
            "condition": "#DDA0DD",
            "scope": "#98D8C8",
            "purpose": "#F7DC6F"
        }

        for node, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "unknown")
            elements["nodes"].append({
                "data": {
                    "id": node,
                    "label": data.get("label", node),
                    "type": node_type,
                    "color": node_colors.get(node_type, "#CCCCCC")
                }
            })

        for u, v, data in self.graph.edges(data=True):
            elements["edges"].append({
                "data": {
                    "id": f"{u}_{v}",
                    "source": u,
                    "target": v,
                    "label": data.get("edge_type", "")
                }
            })

        return elements


def build_rule_kg(rules: list) -> nx.DiGraph:
    builder = RuleKGBuilder()
    return builder.build_from_rules(rules)