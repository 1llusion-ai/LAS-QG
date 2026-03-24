import re
import json


def parse_kg_txt(txt_path: str) -> list:
    rules = []

    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.strip()

    if content.startswith("["):
        try:
            triples = json.loads(content)
            for i, triple in enumerate(triples):
                rules.append({
                    "id": f"rule_{i}",
                    "label": f"{triple.get('head', '')} {triple.get('relation', '')} {triple.get('tail', '')}",
                    "head": triple.get("head", ""),
                    "relation": triple.get("relation", ""),
                    "tail": triple.get("tail", ""),
                    "doc_title": triple.get("doc_title", ""),
                    "article": triple.get("article", ""),
                    "chunk_id": triple.get("chunk_id", i),
                    "source_text": triple.get("source_text", ""),
                })
            return rules
        except json.JSONDecodeError:
            pass

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line == "{" or (line.startswith("{") and line.endswith("{")):
            json_str = line + "\n"
            depth = line.count("{") - line.count("}")
            j = i + 1

            while j < len(lines) and depth > 0:
                next_line = lines[j]
                json_str += next_line + "\n"
                depth += next_line.strip().count("{") - next_line.strip().count("}")
                j += 1

            try:
                triple = json.loads(json_str.strip())
                if isinstance(triple, dict) and "head" in triple:
                    rules.append({
                        "id": f"rule_{len(rules)}",
                        "label": f"{triple.get('head', '')} {triple.get('relation', '')} {triple.get('tail', '')}",
                        "head": triple.get("head", ""),
                        "relation": triple.get("relation", ""),
                        "tail": triple.get("tail", ""),
                        "doc_title": triple.get("doc_title", ""),
                        "article": triple.get("article", ""),
                        "chunk_id": triple.get("chunk_id", 0),
                        "source_text": triple.get("source_text", ""),
                    })
                    i = j - 1
            except json.JSONDecodeError:
                pass

        i += 1

    return rules
