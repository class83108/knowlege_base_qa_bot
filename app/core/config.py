from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development")
    kb_dir: Path = Field(default=Path(".kb"))
    sqlite_path: Path = Field(default=Path(".kb/knowledge_base.db"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
