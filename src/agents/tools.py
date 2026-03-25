import json
from typing import Optional
from langchain_core.tools import tool

from src.core.neo4j_client import Neo4jClient, get_neo4j_client
from src.core.llm import BaseLLM


_neo4j_client: Optional[Neo4jClient] = None
_llm_client: Optional[BaseLLM] = None


def set_tool_dependencies(neo4j_client: Neo4jClient = None, llm_client: BaseLLM = None):
    global _neo4j_client, _llm_client
    if neo4j_client:
        _neo4j_client = neo4j_client
    if llm_client:
        _llm_client = llm_client


def _get_neo4j_client() -> Neo4jClient:
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = get_neo4j_client()
    return _neo4j_client


def _get_llm_client() -> Optional[BaseLLM]:
    return _llm_client


@tool
def retrieve_chunks(query: str, mode: str = "vector", top_k: int = 5) -> str:
    """
    检索相关文档块。

    Args:
        query: 查询文本
        mode: 检索模式，"vector" 为向量相似度搜索，"keyword" 为关键词搜索
        top_k: 返回的最大文档块数量

    Returns:
        JSON字符串，包含检索到的文档块列表
    """
    try:
        client = _get_neo4j_client()
        llm = _get_llm_client()

        if mode == "vector":
            if llm is None:
                return json.dumps({"error": "LLM客户端未设置，无法生成embedding"}, ensure_ascii=False)

            query_embedding = llm.embed(query)
            chunks = client.similarity_search(query_embedding, top_k=top_k)
        else:
            chunks = _keyword_search(client, query, top_k)

        return json.dumps({
            "status": "success",
            "chunks": chunks,
            "count": len(chunks)
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"检索失败: {str(e)}"}, ensure_ascii=False)


def _keyword_search(client: Neo4jClient, query: str, top_k: int) -> list:
    return client.bm25_search(query, top_k)


@tool
def retrieve_subgraph(chunk_key: str = None, entity_names: list[str] = None, hops: int = 1) -> str:
    """
    检索局部知识图谱子图。

    Args:
        chunk_key: 文档块的key，用于从该块扩展子图
        entity_names: 实体名称列表，用于从实体扩展子图
        hops: 扩展的跳数，默认为1

    Returns:
        JSON字符串，包含子图的实体和关系
    """
    try:
        client = _get_neo4j_client()
        subgraph = {
            "chunk": None,
            "entities": [],
            "relations": []
        }

        if chunk_key:
            result = client.expand_subgraph(chunk_key, hops)
            subgraph = result

        if entity_names:
            entities, relations = _expand_from_entities(client, entity_names, hops)
            subgraph["entities"].extend(entities)
            subgraph["relations"].extend(relations)

        unique_entities = {e["name"]: e for e in subgraph["entities"]}
        subgraph["entities"] = list(unique_entities.values())

        return json.dumps({
            "status": "success",
            "subgraph": subgraph
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"子图检索失败: {str(e)}"}, ensure_ascii=False)


def _expand_from_entities(client: Neo4jClient, entity_names: list[str], hops: int) -> tuple:
    from neo4j import GraphDatabase

    driver = client._get_driver()
    entities = []
    relations = []

    with driver.session() as session:
        for name in entity_names[:5]:
            cypher = """
            MATCH (e:Entity {name: $name})
            OPTIONAL MATCH (e)-[r:RELATION]-(other:Entity)
            RETURN e.name as entity_name, collect(DISTINCT other.name) as related_entities,
                   collect(DISTINCT {start: startNode(r).name, end: endNode(r).name,
                                      text: r.relation_text, article: r.article}) as rels
            """
            cursor = session.run(cypher, name=name)
            record = cursor.single()

            if record:
                entities.append({"name": record.get("entity_name", "")})
                for related in record.get("related_entities", []):
                    if related:
                        entities.append({"name": related})

                for rel in record.get("rels", []):
                    if rel and rel.get("start") and rel.get("end"):
                        relations.append({
                            "head": rel.get("start", ""),
                            "tail": rel.get("end", ""),
                            "relation_text": rel.get("text", ""),
                            "article": rel.get("article", ""),
                        })

    return entities, relations


@tool
def generate_questions(
    subgraph: dict,
    question_type: str = "choice",
    difficulty: str = "medium",
    hop_depth: int = 1
) -> str:
    """
    基于知识图谱子图生成问题。

    Args:
        subgraph: 子图信息，包含 entities, relations, chunk 等
        question_type: 题型，"choice" 为选择题，"judgment" 为判断题
        difficulty: 难度，"easy"、"medium" 或 "hard"
        hop_depth: 子图多跳深度

    Returns:
        JSON字符串，包含生成的问题
    """
    try:
        from src.agents.prompts import QUESTION_GENERATION_PROMPT

        llm = _get_llm_client()

        if llm is None:
            return json.dumps({"error": "LLM客户端未设置"}, ensure_ascii=False)

        difficulty_desc = {
            "easy": "简单",
            "medium": "中等",
            "hard": "困难"
        }

        type_desc = {
            "choice": "选择题",
            "judgment": "判断题"
        }

        entities = subgraph.get("entities", [])
        relations = subgraph.get("relations", [])
        chunk = subgraph.get("chunk", {})

        entities_text = "\n".join([
            f"- {e.get('name', e) if isinstance(e, dict) else e}"
            for e in entities[:20]
        ]) if entities else "无"

        relations_text = "\n".join([
            f"- {r.get('head', '')} --[{r.get('relation_text', '')}]--> {r.get('tail', '')}"
            for r in relations[:20]
        ]) if relations else "无"

        context_text = chunk.get("source_text", "")[:2000] if chunk else "无原文上下文"

        prompt = QUESTION_GENERATION_PROMPT.format(
            difficulty=difficulty_desc.get(difficulty, "中等"),
            question_type=type_desc.get(question_type, "选择题"),
            hop_depth=hop_depth,
            entity_count=len(entities),
            relation_count=len(relations),
            entities_text=entities_text,
            relations_text=relations_text,
            context_text=context_text
        )

        response = llm.generate(prompt, temperature=0.7, max_tokens=1000)

        try:
            question_data = json.loads(response)
        except json.JSONDecodeError:
            question_data = _parse_question_response(response)

        question_data["question_type"] = question_type
        question_data["difficulty"] = difficulty

        return json.dumps({
            "status": "success",
            "question": question_data
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"问题生成失败: {str(e)}"}, ensure_ascii=False)


def _parse_question_response(response: str) -> dict:
    import re

    question_text = ""
    answer = ""
    explanation = ""
    options = []

    q_match = re.search(r"题目[：:]\s*(.+?)(?=\n|选项|答案|$)", response, re.DOTALL)
    if q_match:
        question_text = q_match.group(1).strip()

    a_match = re.search(r"答案[：:]\s*(.+?)(?=\n|解释|$)", response)
    if a_match:
        answer = a_match.group(1).strip()

    e_match = re.search(r"解释[：:]\s*(.+?)(?=\n|$)", response, re.DOTALL)
    if e_match:
        explanation = e_match.group(1).strip()

    return {
        "question_text": question_text,
        "options": options,
        "answer": answer,
        "explanation": explanation
    }


@tool
def evaluate_questions(question: dict, requirements: dict = None) -> str:
    """
    评估问题质量。

    Args:
        question: 待评估的问题，包含question_text、answer、explanation等字段
        requirements: 评估要求，可包含min_length、max_length、must_include_keywords等

    Returns:
        JSON字符串，包含评估结果、问题点和建议动作
    """
    try:
        llm = _get_llm_client()

        if requirements is None:
            requirements = {}

        question_text = question.get("question_text", "")
        answer = question.get("answer", "")
        explanation = question.get("explanation", "")
        difficulty = question.get("difficulty", "medium")

        issues = []
        suggestions = []

        if len(question_text) < 10:
            issues.append("题目文本过短")
            suggestions.append("扩展题目内容，增加具体情境")

        if not answer:
            issues.append("缺少答案")
            suggestions.append("提供明确的答案")

        if len(explanation) < 20:
            issues.append("解释过于简短")
            suggestions.append("补充详细解释，说明答案依据")

        must_include = requirements.get("must_include_keywords", [])
        if must_include:
            for keyword in must_include:
                if keyword not in question_text and keyword not in explanation:
                    issues.append(f"缺少关键词: {keyword}")

        if llm:
            llm_evaluation = _llm_evaluate(llm, question, difficulty)
            if llm_evaluation:
                issues.extend(llm_evaluation.get("issues", []))
                suggestions.extend(llm_evaluation.get("suggestions", []))

        is_approved = len(issues) == 0

        suggested_action = "approve" if is_approved else "regenerate"

        return json.dumps({
            "status": "success",
            "is_approved": is_approved,
            "issues": issues,
            "suggestions": suggestions,
            "suggested_action": suggested_action,
            "quality_score": 1.0 if is_approved else 0.5
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"评估失败: {str(e)}"}, ensure_ascii=False)


def _llm_evaluate(llm: BaseLLM, question: dict, difficulty: str) -> dict:
    prompt = f"""请评估以下低空安全题目的质量。

题目：{question.get('question_text', '')}
答案：{question.get('answer', '')}
解释：{question.get('explanation', '')}
目标难度：{difficulty}

请从以下维度评估：
1. 题目表述是否清晰
2. 答案是否正确明确
3. 解释是否充分
4. 难度是否匹配

请以JSON格式输出：
{{
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}}

如果没有问题，输出空列表。
"""

    try:
        response = llm.generate(prompt, temperature=0.3, max_tokens=500)
        return json.loads(response)
    except Exception:
        return {"issues": [], "suggestions": []}


def get_all_tools():
    return [
        retrieve_chunks,
        retrieve_subgraph,
        generate_questions,
        evaluate_questions,
    ]
