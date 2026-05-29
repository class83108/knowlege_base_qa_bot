from fastapi import APIRouter, Request

from app.services.indexing import IndexingService

router = APIRouter(tags=["index"])


@router.post("/index")
def rebuild_index(request: Request) -> dict:
    settings = request.app.state.settings
    service = IndexingService(
        docs_dir=settings.docs_dir,
        manifest_path=settings.kb_dir / "index.json",
        database_path=settings.sqlite_path,
        max_chunk_chars=1_000,
    )
    return service.rebuild_index()
