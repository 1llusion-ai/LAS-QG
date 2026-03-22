from typing import Optional, Literal
from src.schemas.types import RuleKnowledgeGraph, DocumentChunk
from src.generation.llm_client import BaseLLM, MockLLM
from src.kg.rule_extractor import RuleKGExtractor, extract_rule_kg


class ExtractionAgent:
    def __init__(self, llm: Optional[BaseLLM] = None, max_retries: int = 2):
        self.llm = llm or MockLLM()
        self.max_retries = max_retries
        self.extractor = RuleKGExtractor(self.llm)

    def run(self, document_id: str, chunks: list[DocumentChunk]) -> dict:
        result = {
            "status": "init",
            "rule_kg": None,
            "error": None,
            "retry_count": 0,
            "chunks_processed": 0,
        }

        for attempt in range(self.max_retries + 1):
            try:
                rule_kg = extract_rule_kg(document_id, chunks, self.llm)
                result["status"] = "success"
                result["rule_kg"] = rule_kg
                result["chunks_processed"] = len(chunks)
                return result

            except Exception as e:
                result["retry_count"] = attempt + 1
                result["error"] = str(e)

                if attempt >= self.max_retries:
                    result["status"] = "failed"
                    fallback_kg = self._fallback_extract(document_id, chunks)
                    result["rule_kg"] = fallback_kg
                    result["status"] = "fallback"
                    return result

        return result

    def _fallback_extract(self, document_id: str, chunks: list[DocumentChunk]) -> RuleKnowledgeGraph:
        return extract_rule_kg(document_id, chunks, llm=None)


class QuestionGenerationAgent:
    def __init__(self, llm: Optional[BaseLLM] = None, max_retries: int = 2):
        self.llm = llm or MockLLM()
        self.max_retries = max_retries

    def run(self, prompt: str, expected_format: Optional[type] = None) -> dict:
        result = {
            "status": "init",
            "response": None,
            "error": None,
            "retry_count": 0,
        }

        for attempt in range(self.max_retries + 1):
            try:
                response = self.llm.generate(prompt)
                result["status"] = "success"
                result["response"] = response
                return result

            except Exception as e:
                result["retry_count"] = attempt + 1
                result["error"] = str(e)

                if attempt >= self.max_retries:
                    result["status"] = "failed"
                    return result

        return result


class EvaluationAgent:
    def __init__(self, llm: Optional[BaseLLM] = None, max_retries: int = 2):
        self.llm = llm or MockLLM()
        self.max_retries = max_retries

    def run(self, question_text: str, answer: str, explanation: str, difficulty: str) -> dict:
        result = {
            "status": "init",
            "evaluation": None,
            "error": None,
            "retry_count": 0,
        }

        prompt = f"""评估以下问题：
问题：{question_text}
答案：{answer}
解释：{explanation}
难度：{difficulty}

请返回JSON格式的评估结果：
{{"quality_score": 0.0-1.0, "difficulty_consistency": 0.0-1.0, "feedback": "反馈"}}
"""

        for attempt in range(self.max_retries + 1):
            try:
                response = self.llm.generate(prompt)
                import json
                eval_data = json.loads(response)
                result["status"] = "success"
                result["evaluation"] = eval_data
                return result

            except Exception as e:
                result["retry_count"] = attempt + 1
                result["error"] = str(e)

                if attempt >= self.max_retries:
                    result["status"] = "failed"
                    return result

        return result


def get_extraction_agent(llm: Optional[BaseLLM] = None) -> ExtractionAgent:
    return ExtractionAgent(llm)


def get_question_generation_agent(llm: Optional[BaseLLM] = None) -> QuestionGenerationAgent:
    return QuestionGenerationAgent(llm)


def get_evaluation_agent(llm: Optional[BaseLLM] = None) -> EvaluationAgent:
    return EvaluationAgent(llm)
