from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.index import router as index_router
from app.core.config import get_settings
from app.db.session import initialize_database


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
) -> FastAPI:
    settings = get_settings().model_copy(
        update={
            "docs_dir": docs_dir or get_settings().docs_dir,
            "kb_dir": kb_dir or get_settings().kb_dir,
            "sqlite_path": sqlite_path or get_settings().sqlite_path,
        }
    )
    app = FastAPI(
        title="Knowledge Base Q&A Bot",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(health_router)
    app.include_router(index_router)
    return app


app = create_app()
