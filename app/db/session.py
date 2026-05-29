from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.db.raw_index_repository import initialize_raw_index_schema

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            f"sqlite:///{settings.sqlite_path}",
            future=True,
        )
    return _engine


def initialize_database(database_path: Path | None = None) -> None:
    if database_path is None:
        database_path = get_settings().sqlite_path
    initialize_raw_index_schema(database_path)
