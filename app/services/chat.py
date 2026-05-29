from __future__ import annotations

from pathlib import Path

from app.db.raw_index_repository import QueryRecord, RawIndexRepository
from app.domain.raw_evidence_selector import select_raw_evidence


class ChatService:
    def __init__(self, *, database_path: Path) -> None:
        self._repository = RawIndexRepository(database_path)

    def answer(self, query: str) -> dict:
        if not self._repository.has_active_index():
            response = {
                "status": "not_indexed",
                "retrieval_mode": "none",
                "answer": "",
                "citations": [],
                "used_cards": [],
                "used_raw_sections": [],
                "message": "The knowledge base has not been indexed yet.",
            }
            self._log_query(query, response)
            return response

        results = self._repository.search_raw_sections(query, limit=3)
        evidence = select_raw_evidence(
            query=query,
            results=results,
            max_sections=3,
            max_total_tokens=200,
        )
        if not evidence.sections:
            response = {
                "status": "cannot_confirm",
                "retrieval_mode": "none",
                "answer": "I cannot confirm the answer from the knowledge base.",
                "citations": [],
                "used_cards": [],
                "used_raw_sections": [],
                "message": "No sufficiently supported answer was found.",
            }
            self._log_query(query, response)
            return response

        if not evidence.has_meaningful_overlap:
            response = {
                "status": "cannot_confirm",
                "retrieval_mode": "none",
                "answer": "I cannot confirm the answer from the knowledge base.",
                "citations": [],
                "used_cards": [],
                "used_raw_sections": [],
                "message": "No sufficiently supported answer was found.",
            }
            self._log_query(query, response)
            return response
        citations = [section.citation for section in evidence.sections]
        response = {
            "status": "ok",
            "retrieval_mode": "raw",
            "answer": _build_raw_answer(evidence.sections),
            "citations": citations,
            "used_cards": [],
            "used_raw_sections": citations,
            "message": "Answer generated from raw section retrieval.",
        }
        self._log_query(query, response)
        return response

    def _log_query(self, query: str, response: dict) -> None:
        self._repository.log_query_record(
            QueryRecord(
                query_text=query,
                status=response["status"],
                retrieval_mode=response["retrieval_mode"],
                answer=response["answer"],
                citations=response["citations"],
                used_cards=response["used_cards"],
                used_raw_sections=response["used_raw_sections"],
            )
        )


def _build_raw_answer(sections) -> str:
    return "\n\n".join(section.content for section in sections)
