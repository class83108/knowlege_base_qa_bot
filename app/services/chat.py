from __future__ import annotations

from pathlib import Path

from app.db.raw_index_repository import (
    ConceptCardSearchResult,
    QueryRecord,
    RawIndexRepository,
    RawSectionSearchResult,
)
from app.domain.prompt_builder import build_grounded_answer_prompt
from app.domain.raw_evidence_selector import select_raw_evidence
from app.domain.retrieval_policy import (
    filter_supported_cards,
    is_card_evidence_sufficient,
    is_raw_evidence_sufficient,
)
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

        raw_results = self._repository.search_raw_sections(query, limit=5)
        card_results = self._repository.search_concept_cards(query, limit=3)
        top_card_score = card_results[0].score if card_results else None
        top_raw_score = raw_results[0].score if raw_results else None

        if card_results:
            supported_cards = filter_supported_cards(query, card_results)
            raw_sources = _deduplicate_citations(
                citation for card in supported_cards for citation in card.raw_sources
            )
            card_sections = _select_card_support_sections(
                citations=raw_sources,
                ranked_results=raw_results,
                repository=self._repository,
            )
            if card_sections:
                card_evidence = select_raw_evidence(
                    query=query,
                    results=card_sections,
                    max_sections=3,
                    max_total_tokens=200,
                )
                if is_card_evidence_sufficient(
                    query=query,
                    supported_cards=supported_cards,
                    evidence=card_evidence,
                ):
                    return self._build_card_response(
                        query=query,
                        supported_cards=supported_cards,
                        card_evidence_sections=card_evidence.sections,
                        top_card_score=top_card_score,
                        strongest_evidence_score=card_evidence.strongest_score,
                    )

        raw_evidence = select_raw_evidence(
            query=query,
            results=raw_results,
            max_sections=3,
            max_total_tokens=200,
        )
        if not is_raw_evidence_sufficient(raw_evidence):
            response = {
                "status": "cannot_confirm",
                "retrieval_mode": "none",
                "answer": "I cannot confirm the answer from the knowledge base.",
                "citations": [],
                "used_cards": [],
                "used_raw_sections": [],
                "message": "No sufficiently supported answer was found.",
            }
            self._log_query(query, response, top_card_score=top_card_score, top_raw_score=top_raw_score)
            return response

        return self._build_raw_response(
            query=query,
            raw_evidence_sections=raw_evidence.sections,
            top_card_score=top_card_score,
            strongest_evidence_score=raw_evidence.strongest_score,
        )

    def _build_card_response(
        self,
        *,
        query: str,
        supported_cards: list[ConceptCardSearchResult],
        card_evidence_sections: list[RawSectionSearchResult],
        top_card_score: float | None,
        strongest_evidence_score: float,
    ) -> dict:
        prompt = build_grounded_answer_prompt(query=query, sections=card_evidence_sections)
        grounded_answer = parse_grounded_answer_response(self._answer_generator.generate(prompt))
        allowed_citations = {section.citation for section in card_evidence_sections}
        response_citations = [c for c in grounded_answer.citations if c in allowed_citations]
        ok = grounded_answer.status == "ok"
        response = {
            "status": grounded_answer.status,
            "retrieval_mode": "cards" if ok else "none",
            "answer": grounded_answer.answer,
            "citations": response_citations,
            "used_cards": _used_card_titles(cards=supported_cards, citations=response_citations) if ok else [],
            "used_raw_sections": response_citations if ok else [],
            "message": "Answer generated from concept card retrieval with raw support.",
        }
        self._log_query(query, response, top_card_score=top_card_score, top_raw_score=strongest_evidence_score)
        return response

    def _build_raw_response(
        self,
        *,
        query: str,
        raw_evidence_sections: list[RawSectionSearchResult],
        top_card_score: float | None,
        strongest_evidence_score: float,
    ) -> dict:
        citations = [section.citation for section in raw_evidence_sections]
        prompt = build_grounded_answer_prompt(query=query, sections=raw_evidence_sections)
        grounded_answer = parse_grounded_answer_response(self._answer_generator.generate(prompt))
        ok = grounded_answer.status == "ok"
        response_citations = [c for c in grounded_answer.citations if c in citations] if ok else []
        response = {
            "status": grounded_answer.status,
            "retrieval_mode": "raw" if ok else "none",
            "answer": grounded_answer.answer,
            "citations": response_citations,
            "used_cards": [],
            "used_raw_sections": response_citations,
            "message": "Answer generated from raw section retrieval.",
        }
        self._log_query(query, response, top_card_score=top_card_score, top_raw_score=strongest_evidence_score)
        return response

    def _log_query(
        self,
        query: str,
        response: dict,
        *,
        top_card_score: float | None = None,
        top_raw_score: float | None = None,
    ) -> None:
        self._repository.log_query_record(
            QueryRecord(
                query_text=query,
                status=response["status"],
                retrieval_mode=response["retrieval_mode"],
                answer=response["answer"],
                citations=response["citations"],
                used_cards=response["used_cards"],
                used_raw_sections=response["used_raw_sections"],
                top_card_score=top_card_score,
                top_raw_score=top_raw_score,
            )
        )


def _deduplicate_citations(citations) -> list[str]:
    return list(dict.fromkeys(citations))


def _select_card_support_sections(
    *,
    citations: list[str],
    ranked_results: list[RawSectionSearchResult],
    repository: RawIndexRepository,
) -> list[RawSectionSearchResult]:
    ranked_by_citation = {
        section.citation: section for section in ranked_results if section.citation in citations
    }
    missing_citations = [c for c in citations if c not in ranked_by_citation]
    fallback_by_citation = {
        section.citation: section
        for section in repository.get_raw_sections_by_citations(missing_citations)
    }
    return [
        ranked_by_citation.get(citation) or fallback_by_citation[citation]
        for citation in citations
        if citation in ranked_by_citation or citation in fallback_by_citation
    ]


def _used_card_titles(
    *,
    cards: list[ConceptCardSearchResult],
    citations: list[str],
) -> list[str]:
    citation_set = set(citations)
    return [card.title for card in cards if citation_set.intersection(card.raw_sources)]
