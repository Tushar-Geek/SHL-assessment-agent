from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SHL Assessment Recommendation Agent"
    catalog_path: Path = Field(default=BASE_DIR / "data" / "catalog.json")
    index_dir: Path = Field(default=BASE_DIR / "data" / "index")
    top_k: int = 10
    min_query_chars: int = 12
    request_timeout_seconds: float = 20.0

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4.1-mini"
    use_llm: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
