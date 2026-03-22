import re


def parse_kg_txt(txt_path: str) -> list:
    rules = []
    current_rule = None

    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("Chunk "):
            i += 1
            continue

        if line.startswith("【规则】"):
            i += 1
            continue

        if line.startswith("- "):
            if current_rule:
                rules.append(current_rule)

            rule_label = line[2:].strip()
            current_rule = {
                "id": f"rule_{len(rules)}",
                "label": rule_label,
                "subjects": [],
                "action": None,
                "objects": [],
                "modality": None,
                "condition_text": None,
                "basis_text": None,
                "scope_text": None,
                "purpose_text": None,
                "evidence_text": None,
                "source_chunk_id": None,
                "article_no": None
            }

            i += 1
            continue

        if current_rule:
            if line.startswith("主体:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["subjects"] = [s.strip() for s in value.split("、") if s.strip()]

            elif line.startswith("动作:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["action"] = value

            elif line.startswith("对象:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["objects"] = [o.strip() for o in value.split("、") if o.strip()]

            elif line.startswith("情态:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["modality"] = value

            elif line.startswith("条件:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["condition_text"] = value

            elif line.startswith("依据:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["basis_text"] = value

            elif line.startswith("范围:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["scope_text"] = value

            elif line.startswith("目的:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["purpose_text"] = value

            elif line.startswith("原文:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["evidence_text"] = value

            elif line.startswith("来源:"):
                value = line[3:].strip()
                if value != "无":
                    current_rule["article_no"] = value

        i += 1

    if current_rule:
        rules.append(current_rule)

    return rules