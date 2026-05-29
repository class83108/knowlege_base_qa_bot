from fastapi import APIRouter, Request

from app.models.chat import ChatRequest
from app.services.answer_generation import build_answer_generator
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat")
def chat(request: Request, payload: ChatRequest) -> dict:
    settings = request.app.state.settings
    answer_generator = build_answer_generator(
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
    )
    service = ChatService(
        database_path=settings.sqlite_path,
        answer_generator=answer_generator,
    )
    return service.answer(payload.query)
