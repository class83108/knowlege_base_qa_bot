from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.db.session import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.kb_dir.mkdir(parents=True, exist_ok=True)
    initialize_database()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Knowledge Base Q&A Bot",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    return app


app = create_app()
