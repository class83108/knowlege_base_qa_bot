from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.index import router as index_router
from app.api.routes.query_records import router as query_records_router
from app.core.config import get_settings
from app.db.session import initialize_database

_UNSET = object()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    settings.kb_dir.mkdir(parents=True, exist_ok=True)
    initialize_database(settings.sqlite_path)
    yield


def create_app(
    *,
    docs_dir: Path | None = None,
    kb_dir: Path | None = None,
    sqlite_path: Path | None = None,
    openai_api_key: str | None | object = _UNSET,
    openai_model: str | object = _UNSET,
) -> FastAPI:
    base_settings = get_settings()
    update = {
        "docs_dir": docs_dir or base_settings.docs_dir,
        "kb_dir": kb_dir or base_settings.kb_dir,
        "sqlite_path": sqlite_path or base_settings.sqlite_path,
    }
    if openai_api_key is not _UNSET:
        update["openai_api_key"] = openai_api_key
    if openai_model is not _UNSET:
        update["openai_model"] = openai_model
    settings = base_settings.model_copy(update=update)
    app = FastAPI(
        title="Knowledge Base Q&A Bot",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(index_router)
    app.include_router(chat_router)
    app.include_router(query_records_router)
    return app


app = create_app()
