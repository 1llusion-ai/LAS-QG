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


EXTRACTION_PROMPT = """
你是一个信息抽取系统（DeepIE风格）。

你的任务是：从输入的低空安全领域法律文本中抽取“实体-关系-实体”三元组。

================================
【输出格式】

[
{
  "head": "...",
  "relation": "...",
  "tail": "...",
}
]

================================
【核心抽取规则】

1. 三元组定义：
- head：主体实体
- relation：关系（动作）
- tail：客体实体

--------------------------------
2. 实体要求：
- 必须来自原文
- 必须是完整语义单位
- 不使用“其 / 该 / 本”等代词
- 尽量具体

--------------------------------
3. 关系要求（重要）：
- 使用语义明确动词
- 推荐：
  监督管理、批准、编制、纳入、保护、办理审批、提出申请、
  责令改正、罚款、行政拘留、应当具备、衔接、
  罚款金额、拘留期限、没收对象、吊销期限、暂扣期限

- 禁止：
  是、进行、开展、作出（无语义）

--------------------------------
4. 三类条款处理规则

【A 行为类】
主体 → 行为 → 对象

【B 条件类】
主体 → 应当具备 → 每一项条件
❗ 必须展开，不允许丢弃

--------------------------------
【C 处罚类（重点规则）】

必须抽取：

1）违法行为（必须保留原文）
2）处罚主体
3）处罚措施（罚款 / 拘留 / 吊销等）
4）处罚属性（金额 / 时间 / 对象）

--------------------------------
【处罚类强制约束（核心）】

❗ 禁止：

- tail = "违反本条例的行为"
- tail = "违法行为"

❗ 必须：

✔ 使用原文中的具体违法行为描述

--------------------------------
【处罚属性绑定规则（最重要）】

所有处罚属性必须绑定“违法行为”，不能绑定处罚词

✔ 正确：

("某违法行为", "罚款金额", "10万元以上50万元以下")
("某违法行为", "拘留期限", "5日以上10日以下")
("某违法行为", "没收对象", "违法所得")

❌ 错误：

("罚款", "金额", "10万元")
("拘留", "期限", "5日")

--------------------------------
【处罚结构标准（统一）】

对于处罚条款，应输出：

1）处罚机关 → 处罚措施 → 违法行为
2）违法行为 → 处罚属性 → 数值/对象

--------------------------------
5. 多关系规则：
- 并列动作必须拆分
- 条件列表必须拆分
- 一个句子可产生多个三元组

--------------------------------
6. 抽取范围限制：

以下情况返回空数组：

- 纯立法目的（如：制定本条例）
- 纯定义（如：分为）
- 完全无行为关系

⚠️ 注意：
如果句子包含“应当 / 不得 / 处罚 / 条件”，必须抽取

================================
【Few-shot 示例】

示例1（监管）
输入：
国务院民用航空主管部门依法对全国民用机场实施行业监督管理。

输出：
[
{"head": "国务院民用航空主管部门", "relation": "监督管理", "tail": "全国民用机场"}
]

--------------------------------
示例2（条件类）
输入：
企业应当具备下列条件：取得许可，有设备，有人员。

输出：
[
{"head": "企业", "relation": "应当具备", "tail": "许可"},
{"head": "企业", "relation": "应当具备", "tail": "设备"},
{"head": "企业", "relation": "应当具备", "tail": "人员"}
]

--------------------------------
示例3（罚款类）

输入：
在机场区域内违规设置设施，未设置警示标志的，由管理机构责令改正，并处10万元以上50万元以下罚款。

输出：
[
{"head": "管理机构", "relation": "责令改正", "tail": "在机场区域内违规设置设施且未设置警示标志的行为"},
{"head": "管理机构", "relation": "罚款", "tail": "在机场区域内违规设置设施且未设置警示标志的行为"},
{"head": "在机场区域内违规设置设施且未设置警示标志的行为", "relation": "罚款金额", "tail": "10万元以上50万元以下"}
]

--------------------------------
示例4（拘留类）

输入：
有下列行为之一的，处五日以下拘留；情节较重的，处五日以上十日以下拘留。

输出：
[
{"head": "实施相关违法行为的行为", "relation": "拘留期限", "tail": "五日以下"},
{"head": "情节较重的相关违法行为", "relation": "拘留期限", "tail": "五日以上十日以下"}
]

--------------------------------
示例5（负样本）
输入：
为了规范民用机场建设，制定本条例。

输出：
[]

================================
【输入文本】
{text}

================================
只输出 JSON：
"""


class RuleKGExtractor:
    def __init__(self, llm: Optional[BaseLLM] = None, doc_title: str = ""):
        self.llm = llm
        self.doc_title = doc_title

    def extract(self, chunk: DocumentChunk, chunk_index: int = 0) -> dict:
        if self.llm:
            return self._llm_extract(chunk, chunk_index)
        return self._rule_based_extract(chunk, chunk_index)

    def _llm_extract(self, chunk: DocumentChunk, chunk_index: int = 0) -> dict:
        prompt = EXTRACTION_PROMPT.replace("{text}", chunk.content)

        try:
            print(f"\n[LLM抽取] 正在处理 chunk {chunk_index}: {chunk.id[:8]}...")
            print(f"[LLM抽取] 文本片段: {chunk.content[:100]}...")
            
            response = self.llm.generate(prompt)
            
            if response is None:
                print("[LLM抽取] LLM返回None，使用规则抽取")
                return self._rule_based_extract(chunk, chunk_index)

            print(f"[LLM抽取] LLM响应:\n{response[:500]}..." if len(response) > 500 else f"[LLM抽取] LLM响应:\n{response}")

            response_clean = response.strip()
            if not response_clean:
                print("[LLM抽取] 响应为空，使用规则抽取")
                return self._rule_based_extract(chunk, chunk_index)

            response_clean = re.sub(r"^```json\s*", "", response_clean)
            response_clean = re.sub(r"^```\s*", "", response_clean)
            response_clean = re.sub(r"\s*```$", "", response_clean)
            response_clean = response_clean.strip()

            if not response_clean.startswith("[") and not response_clean.startswith("{"):
                print(f"[LLM抽取] 响应格式不正确(不以[或{{开头)，使用规则抽取")
                return self._rule_based_extract(chunk, chunk_index)

            data = json.loads(response_clean)
            result = self._process_extraction_result(data, chunk, self.doc_title, chunk_index)
            print(f"[LLM抽取] 成功抽取 {len(result.get('rules', []))} 条三元组")
            return result
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[LLM抽取] JSON解析错误: {e}，使用规则抽取")
            return self._rule_based_extract(chunk, chunk_index)
        except Exception as e:
            print(f"[LLM抽取] 异常: {type(e).__name__}: {e}，使用规则抽取")
            import traceback
            traceback.print_exc()
            return self._rule_based_extract(chunk, chunk_index)

    def _process_extraction_result(self, data, chunk: DocumentChunk, doc_title: str = "", chunk_index: int = 0) -> dict:
        rules = []

        if isinstance(data, list):
            triples = data
        elif isinstance(data, dict) and "rules" in data:
            triples = data.get("rules", [])
        else:
            return {"rules": rules}

        for triple in triples:
            head = triple.get("head", "")
            relation = triple.get("relation", "")
            tail = triple.get("tail", "")

            if not head or not relation or not tail:
                continue

            label = f"{head} {relation} {tail}"

            source_text = triple.get("source_text") or chunk.content
            article = triple.get("article") or chunk.metadata.get("article_no", "")

            rules.append({
                "id": str(uuid.uuid4()),
                "label": label,
                "head": head,
                "relation": relation,
                "tail": tail,
                "doc_title": triple.get("doc_title") or doc_title,
                "article": article,
                "chunk_id": triple.get("chunk_id") or chunk_index,
                "source_text": source_text,
                "subjects": [head],
                "action": relation,
                "objects": [tail],
                "modality": None,
                "condition_text": None,
                "basis_text": None,
                "scope_text": None,
                "purpose_text": None,
                "evidence_text": source_text,
                "source_chunk_id": chunk.id,
                "article_no": article,
            })

        return {"rules": rules}

    def _rule_based_extract(self, chunk: DocumentChunk, chunk_index: int = 0) -> dict:
        content = chunk.content
        rules = []

        relation_patterns = [
            (r"(.+?)应当(.+?)，", "应当"),
            (r"(.+?)不得(.+?)。", "不得"),
            (r"(.+?)可以(.+?)。", "可以"),
            (r"(.+?)经(.+?)批准", "批准"),
            (r"(.+?)由(.+?)编制", "编制"),
            (r"(.+?)对(.+?)监督管理", "监督管理"),
        ]

        for pattern, relation in relation_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    head = match[0].strip() if match[0] else ""
                    tail = match[1].strip() if match[1] else ""

                    if head and tail and len(head) > 1 and len(tail) > 1:
                        label = f"{head} {relation} {tail}"
                        article = chunk.metadata.get("article_no", "")
                        rules.append({
                            "id": str(uuid.uuid4()),
                            "label": label,
                            "head": head,
                            "relation": relation,
                            "tail": tail,
                            "doc_title": self.doc_title,
                            "article": article,
                            "chunk_id": chunk_index,
                            "source_text": content,
                            "subjects": [head],
                            "action": relation,
                            "objects": [tail],
                            "modality": None,
                            "condition_text": None,
                            "basis_text": None,
                            "scope_text": None,
                            "purpose_text": None,
                            "evidence_text": content,
                            "source_chunk_id": chunk.id,
                            "article_no": article,
                        })

        return {"rules": rules}


def extract_rule_kg(
    document_id: str,
    chunks: list[DocumentChunk],
    llm: Optional[BaseLLM] = None,
    progress_callback: Optional[callable] = None,
    doc_title: str = "",
) -> RuleKnowledgeGraph:
    extractor = RuleKGExtractor(llm, doc_title)

    all_rules = []

    for i, chunk in enumerate(chunks):
        result = extractor.extract(chunk, i)

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