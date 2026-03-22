import json
import uuid
import re
from typing import Optional

from src.schemas.types import (
    RuleKnowledgeGraph,
    Rule,
    DocumentChunk,
)
from src.generation.llm_client import BaseLLM


EXTRACTION_PROMPT = """你是一个法规文本规则抽取助手。你的任务是从文本中抽取"完整的规范性规则"，用于构建规则知识图谱。

=====================
【核心原则（必须严格遵守）】
=====================

1. 规则必须是完整语义单元：
   ✔ 谁，在什么条件下，对什么对象，做什么行为
   ❌ 不允许只输出"应当 / 必须 / 依法"等单词

2. 情态词（依法 / 应当 / 不得 / 可以 / 方可 / 负责）：
   - 只能作为 modality 字段
   - 绝不能单独成为规则

3. 避免过度拆分（非常重要）：
   - 如果多个行为共享同一主体和语境，应合并为一条规则
   - 不要把并列动词机械拆成多条规则

4. 区分"主行为"和"目的"：
   - 主行为：核心动作（如：加强、适用、批准、实施）
   - 目的/结果：如"预防…增进…维护…"
   - 目的应放入 purpose_text，不要拆成独立规则

5. 条件与范围：
   - 条件（如：经批准后、本法没有规定的）→ condition_text
   - 范围（如：在某区域内）→ scope_text

6. 法律依据：
   - 如"根据宪法"、"依照本法" → basis_text

7. 非行为性条文处理：
   - 立法目的、定义性条文，不强行构造规则
   - 如果确实没有行为规则，可以返回空 rules

8. 只基于原文，不允许臆造

9. 信息缺失时：
   - 使用 null
   - 不允许编造

=====================
【输出格式（必须严格一致）】
=====================

{
  "rules": [
    {
      "label": "规则简短描述（≤20字）",
      "subjects": ["主体1", "主体2"],
      "action": "核心行为",
      "objects": ["对象1", "对象2"],
      "modality": "应当|不得|可以|方可|负责|依法|null",
      "condition_text": "条件原文，没有则为 null",
      "basis_text": "法律依据，没有则为 null",
      "scope_text": "适用范围，没有则为 null",
      "purpose_text": "目的或效果，没有则为 null",
      "evidence_text": "原文片段"
    }
  ]
}

=====================
【示例1：简单规则】
=====================

文本：
公安机关及其人民警察依法履行治安管理职责。

输出：
{
  "rules": [
    {
      "label": "依法履行治安管理职责",
      "subjects": ["公安机关", "人民警察"],
      "action": "履行",
      "objects": ["治安管理职责"],
      "modality": "依法",
      "condition_text": null,
      "basis_text": null,
      "scope_text": null,
      "purpose_text": null,
      "evidence_text": "公安机关及其人民警察依法履行治安管理职责。"
    }
  ]
}

=====================
【示例2：条件规则】
=====================

文本：
经民用航空管理部门批准后，方可实施。

输出：
{
  "rules": [
    {
      "label": "批准后方可实施",
      "subjects": [null],
      "action": "实施",
      "objects": [null],
      "modality": "方可",
      "condition_text": "经民用航空管理部门批准后",
      "basis_text": null,
      "scope_text": null,
      "purpose_text": null,
      "evidence_text": "经民用航空管理部门批准后，方可实施。"
    }
  ]
}

=====================
【示例3：避免过度拆分】
=====================

文本：
各级人民政府应当加强社会治安综合治理，采取有效措施，预防和化解社会矛盾纠纷，增进社会和谐，维护社会稳定。

输出：
{
  "rules": [
    {
      "label": "政府加强治安治理维护稳定",
      "subjects": ["各级人民政府"],
      "action": "加强并采取措施",
      "objects": ["社会治安综合治理"],
      "modality": "应当",
      "condition_text": null,
      "basis_text": null,
      "scope_text": null,
      "purpose_text": "预防和化解社会矛盾纠纷，增进社会和谐，维护社会稳定",
      "evidence_text": "各级人民政府应当加强社会治安综合治理，采取有效措施，预防和化解社会矛盾纠纷，增进社会和谐，维护社会稳定。"
    }
  ]
}

=====================
【示例4：补充适用规则】
=====================

文本：
本法没有规定的，适用《中华人民共和国行政处罚法》的有关规定。

输出：
{
  "rules": [
    {
      "label": "未规定时适用行政处罚法",
      "subjects": [null],
      "action": "适用",
      "objects": ["中华人民共和国行政处罚法"],
      "modality": null,
      "condition_text": "本法没有规定的",
      "basis_text": null,
      "scope_text": null,
      "purpose_text": null,
      "evidence_text": "本法没有规定的，适用《中华人民共和国行政处罚法》的有关规定。"
    }
  ]
}

=====================
【重要约束】
=====================

- 不输出 entities / actions / edges
- 不输出解释说明
- 不输出 markdown
- 不输出多余字段
- 不允许只输出"应当""必须""规定"等词

=====================
【待抽取文本】
=====================

{text}

=====================
【输出要求】
=====================

只输出 JSON：
"""


class RuleKGExtractor:
    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm

    def extract(self, chunk: DocumentChunk) -> dict:
        if self.llm:
            return self._llm_extract(chunk)
        return self._rule_based_extract(chunk)

    def _llm_extract(self, chunk: DocumentChunk) -> dict:
        prompt = EXTRACTION_PROMPT.replace("{text}", chunk.content)

        try:
            response = self.llm.generate(prompt)
            if response is None:
                return self._rule_based_extract(chunk)

            response_clean = response.strip()
            if not response_clean:
                return self._rule_based_extract(chunk)

            response_clean = re.sub(r"^```json\s*", "", response_clean)
            response_clean = re.sub(r"^```\s*", "", response_clean)
            response_clean = re.sub(r"\s*```$", "", response_clean)
            response_clean = response_clean.strip()

            if not response_clean.startswith("{"):
                return self._rule_based_extract(chunk)

            data = json.loads(response_clean)
            return self._process_extraction_result(data, chunk)
        except (json.JSONDecodeError, KeyError, TypeError):
            return self._rule_based_extract(chunk)
        except Exception:
            return self._rule_based_extract(chunk)

    def _process_extraction_result(self, data: dict, chunk: DocumentChunk) -> dict:
        rules = []

        for r in data.get("rules", []):
            subjects = r.get("subjects", [])
            if isinstance(subjects, str):
                subjects = [subjects] if subjects else []
            subjects = [s for s in subjects if s is not None and s != "null"]

            objects = r.get("objects", [])
            if isinstance(objects, str):
                objects = [objects] if objects else []
            objects = [o for o in objects if o is not None and o != "null"]

            rules.append({
                "id": str(uuid.uuid4()),
                "label": r.get("label", ""),
                "subjects": subjects,
                "action": r.get("action") if r.get("action") != "null" else None,
                "objects": objects,
                "modality": r.get("modality") if r.get("modality") != "null" else None,
                "condition_text": r.get("condition_text") if r.get("condition_text") != "null" else None,
                "basis_text": r.get("basis_text") if r.get("basis_text") != "null" else None,
                "scope_text": r.get("scope_text") if r.get("scope_text") != "null" else None,
                "purpose_text": r.get("purpose_text") if r.get("purpose_text") != "null" else None,
                "evidence_text": r.get("evidence_text") if r.get("evidence_text") != "null" else None,
                "source_chunk_id": chunk.id,
                "article_no": chunk.metadata.get("article_no", ""),
            })

        return {"rules": rules}

    def _rule_based_extract(self, chunk: DocumentChunk) -> dict:
        content = chunk.content
        rules = []

        rule_keywords = {
            "应当": ["应当", "应该", "需要"],
            "不得": ["不得", "禁止", "严禁", "不能", "不应"],
            "可以": ["可以", "允许", "准许"],
            "方可": ["方可", "才能"],
            "负责": ["负责", "承担责任"],
            "依法": ["依法", "按照法律规定"],
        }

        for modality, keywords in rule_keywords.items():
            for keyword in keywords:
                if keyword in content:
                    rules.append({
                        "id": str(uuid.uuid4()),
                        "label": f"规则：{keyword}",
                        "subjects": [],
                        "action": None,
                        "objects": [],
                        "modality": modality,
                        "condition_text": None,
                        "basis_text": None,
                        "scope_text": None,
                        "purpose_text": None,
                        "evidence_text": f"从文本中识别的规则词：{keyword}",
                        "source_chunk_id": chunk.id,
                        "article_no": chunk.metadata.get("article_no", ""),
                    })
                    break

        return {"rules": rules}


def extract_rule_kg(
    document_id: str,
    chunks: list[DocumentChunk],
    llm: Optional[BaseLLM] = None,
    progress_callback: Optional[callable] = None,
) -> RuleKnowledgeGraph:
    extractor = RuleKGExtractor(llm)

    all_rules = []

    for i, chunk in enumerate(chunks):
        result = extractor.extract(chunk)

        for r in result.get("rules", []):
            all_rules.append(Rule(**r))

        if progress_callback:
            progress_callback(i + 1, len(chunks), chunk, result)

    all_rules = _deduplicate_by_label(all_rules)

    return RuleKnowledgeGraph(
        document_id=document_id,
        rules=all_rules,
    )


def _deduplicate_by_label(items: list) -> list:
    seen = {}
    result = []
    for item in items:
        if item.label not in seen:
            seen[item.label] = item
            result.append(item)
    return result