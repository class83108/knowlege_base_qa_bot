from fastapi import APIRouter, Request

from app.models.chat import ChatRequest
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat")
def chat(request: Request, payload: ChatRequest) -> dict:
    settings = request.app.state.settings
    service = ChatService(database_path=settings.sqlite_path)
    return service.answer(payload.query)
