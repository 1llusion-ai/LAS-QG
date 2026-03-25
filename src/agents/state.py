from typing import TypedDict, Optional, Annotated
from enum import Enum


class AgentStep(str, Enum):
    INIT = "init"
    RETRIEVE_CHUNKS = "retrieve_chunks"
    RETRIEVE_SUBGRAPH = "retrieve_subgraph"
    GENERATE = "generate"
    EVALUATE = "evaluate"
    COMPLETE = "complete"
    ERROR = "error"


def add_messages(left: list, right: list) -> list:
    return left + right


class QuestionAgentState(TypedDict):
    user_query: str
    current_step: AgentStep
    chunks: list[dict]
    subgraph: dict
    questions: list[dict]
    current_question: Optional[dict]
    evaluation: Optional[dict]
    difficulty: str
    question_type: str
    num_questions: int
    error: Optional[str]
    messages: Annotated[list, add_messages]
    iteration_count: int
    max_iterations: int


def create_initial_agent_state(
    user_query: str,
    difficulty: str = "medium",
    question_type: str = "choice",
    num_questions: int = 1,
    max_iterations: int = 5,
) -> QuestionAgentState:
    return QuestionAgentState(
        user_query=user_query,
        current_step=AgentStep.INIT,
        chunks=[],
        subgraph={},
        questions=[],
        current_question=None,
        evaluation=None,
        difficulty=difficulty,
        question_type=question_type,
        num_questions=num_questions,
        error=None,
        messages=[],
        iteration_count=0,
        max_iterations=max_iterations,
    )
