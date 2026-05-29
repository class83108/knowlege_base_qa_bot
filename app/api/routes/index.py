from fastapi import APIRouter, Request

from app.services.card_generation import build_card_generator
from app.services.indexing import IndexingService

router = APIRouter(tags=["index"])


@router.post("/index")
def rebuild_index(request: Request) -> dict:
    settings = request.app.state.settings
    card_generator = build_card_generator(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
    )
    service = IndexingService(
        docs_dir=settings.docs_dir,
        manifest_path=settings.kb_dir / "index.json",
        database_path=settings.sqlite_path,
        max_chunk_chars=1_000,
        card_generator=card_generator,
    )
    return service.rebuild_index()
