import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass


class LLMConfig(BaseModel):
    provider: str = "siliconflow"
    api_key: Optional[str] = None
    base_url: Optional[str] = "https://api.siliconflow.cn/v1"
    model: str = "deepseek-ai/DeepSeek-V3"
    temperature: float = 0.7
    max_tokens: int = 2000


class ChunkConfig(BaseModel):
    chunk_size: int = 800
    overlap: int = 50


class StorageConfig(BaseModel):
    db_path: str = "data/question_bank.db"
    upload_dir: str = "data/uploads"


class KGConfig(BaseModel):
    entity_types: list[str] = [
        "REGULATION",
        "ALTITUDE",
        "DISTANCE",
        "LOCATION",
        "AIRCRAFT",
        "PERSON",
        "ORGANIZATION",
        "TIME",
        "EQUIPMENT",
    ]
    relation_types: list[str] = [
        "regulates",
        "requires",
        "prohibits",
        "specifies",
        "applies_to",
        "located_at",
        "operated_by",
        "connected_to",
        "altitude_restriction",
        "distance_restriction",
        "time_restriction",
        "must_maintain",
        "must_not_exceed",
    ]
    node_colors: dict[str, str] = {
        "entity": "#4ECDC4",
        "chunk": "#FF6B6B"
    }


class EvaluationConfig(BaseModel):
    quality_threshold: float = 0.6
    difficulty_threshold: float = 0.6
    max_retries: int = 1


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    chunk: ChunkConfig = ChunkConfig()
    storage: StorageConfig = StorageConfig()
    kg: KGConfig = KGConfig()
    evaluation: EvaluationConfig = EvaluationConfig()


def load_config() -> AppConfig:
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if api_key:
        config = AppConfig()
        config.llm.api_key = api_key
        return config
    return AppConfig()


def get_config() -> AppConfig:
    return load_config()


_config: Optional[AppConfig] = None


def get_global_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_global_config(config: AppConfig):
    global _config
    _config = config
