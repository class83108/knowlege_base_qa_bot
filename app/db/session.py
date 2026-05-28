from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

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


def initialize_database() -> None:
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("SELECT 1"))
