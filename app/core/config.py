from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development")
    docs_dir: Path = Field(default=Path("docs"))
    kb_dir: Path = Field(default=Path(".kb"))
    sqlite_path: Path = Field(default=Path(".kb/knowledge_base.db"))
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-5.4-mini")


@lru_cache
def get_settings() -> Settings:
    return Settings()
