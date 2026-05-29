from fastapi import APIRouter, Request

from app.db.raw_index_repository import RawIndexRepository

router = APIRouter(tags=["query-records"])


@router.get("/query-records")
def list_query_records(request: Request) -> list[dict]:
    settings = request.app.state.settings
    if not settings.sqlite_path.exists():
        return []
    repository = RawIndexRepository(settings.sqlite_path)
    return [
        {
            "query_text": record.query_text,
            "status": record.status,
            "retrieval_mode": record.retrieval_mode,
            "answer": record.answer,
            "citations": record.citations,
            "used_cards": record.used_cards,
            "used_raw_sections": record.used_raw_sections,
            "top_card_score": record.top_card_score,
            "top_raw_score": record.top_raw_score,
            "decision_reason": record.decision_reason,
            "candidate_cards": record.candidate_cards,
            "supported_cards": record.supported_cards,
            "card_support_sections": record.card_support_sections,
            "raw_candidate_sections": record.raw_candidate_sections,
            "raw_evidence_sections": record.raw_evidence_sections,
            "latency_ms": record.latency_ms,
            "input_tokens": record.input_tokens,
            "output_tokens": record.output_tokens,
        }
        for record in repository.list_query_records()
    ]
