from __future__ import annotations

from pathlib import Path

from app.db.raw_index_repository import QueryRecord, RawIndexRepository
from app.domain.prompt_builder import build_grounded_answer_prompt
from app.domain.raw_evidence_selector import select_raw_evidence
from app.services.answer_generation import (
    AnswerGenerator,
    EchoEvidenceGenerator,
    parse_grounded_answer_response,
)


class ChatService:
    def __init__(
        self,
        *,
        database_path: Path,
        repository: RawIndexRepository | None = None,
        answer_generator: AnswerGenerator | None = None,
    ) -> None:
        self._repository = repository or RawIndexRepository(database_path)
        self._answer_generator = answer_generator or EchoEvidenceGenerator()

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

        card_results = self._repository.search_concept_cards(query, limit=3)
        if card_results:
            top_card = card_results[0]
            prompt = build_grounded_answer_prompt(
                query=query,
                sections=[
                    type("CardSection", (), {
                        "citation": raw_source,
                        "content": top_card.summary,
                    })()
                    for raw_source in top_card.raw_sources
                ],
            )
            grounded_answer = parse_grounded_answer_response(
                self._answer_generator.generate(prompt)
            )
            response = {
                "status": grounded_answer.status,
                "retrieval_mode": "cards" if grounded_answer.status == "ok" else "none",
                "answer": grounded_answer.answer,
                "citations": [
                    citation
                    for citation in grounded_answer.citations
                    if citation in top_card.raw_sources
                ],
                "used_cards": [top_card.title] if grounded_answer.status == "ok" else [],
                "used_raw_sections": (
                    [
                        citation
                        for citation in grounded_answer.citations
                        if citation in top_card.raw_sources
                    ]
                    if grounded_answer.status == "ok"
                    else []
                ),
                "message": "Answer generated from concept card retrieval.",
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
        prompt = build_grounded_answer_prompt(
            query=query,
            sections=evidence.sections,
        )
        grounded_answer = parse_grounded_answer_response(
            self._answer_generator.generate(prompt)
        )
        response_status = grounded_answer.status
        response_citations = [
            citation for citation in grounded_answer.citations if citation in citations
        ]
        response = {
            "status": response_status,
            "retrieval_mode": "raw" if response_status == "ok" else "none",
            "answer": grounded_answer.answer,
            "citations": response_citations,
            "used_cards": [],
            "used_raw_sections": response_citations if response_status == "ok" else [],
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
