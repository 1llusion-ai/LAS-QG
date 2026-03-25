import json
import uuid
import re
from typing import Optional

from src.schemas.types import (
    RuleKnowledgeGraph,
    Rule,
    DocumentChunk,
)
from src.core.llm import BaseLLM
from src.agents.prompts import EXTRACTION_PROMPT


class RuleKGExtractor:
    def __init__(self, llm: Optional[BaseLLM] = None, doc_title: str = ""):
        self.llm = llm
        self.doc_title = doc_title

    def extract(self, chunk: DocumentChunk, chunk_index: int = 0) -> dict:
        if self.llm:
            print(f"[KG抽取] 使用 LLM 模式处理 chunk {chunk_index}")
            return self._llm_extract(chunk, chunk_index)
        print(f"[KG抽取] 使用规则模式处理 chunk {chunk_index}（未传入 LLM）")
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

            source_text = triple.get("source_text") or chunk.content
            article = triple.get("article") or chunk.metadata.get("article_no", "")

            rules.append({
                "id": str(uuid.uuid4()),
                "head": head,
                "relation": relation,
                "tail": tail,
                "doc_title": triple.get("doc_title") or doc_title,
                "article": article,
                "chunk_id": triple.get("chunk_id") or chunk_index,
                "source_text": source_text,
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
                        article = chunk.metadata.get("article_no", "")
                        rules.append({
                            "id": str(uuid.uuid4()),
                            "head": head,
                            "relation": relation,
                            "tail": tail,
                            "doc_title": self.doc_title,
                            "article": article,
                            "chunk_id": chunk_index,
                            "source_text": content,
                        })

        return {"rules": rules}


def extract_rules(
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
