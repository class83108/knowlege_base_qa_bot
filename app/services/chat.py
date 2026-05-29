from __future__ import annotations

from pathlib import Path
from time import perf_counter

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
        started_at = perf_counter()
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
            self._log_query(
                query,
                response,
                decision_reason="not_indexed",
                latency_ms=_elapsed_ms(started_at),
            )
            return response

        raw_results = self._repository.search_raw_sections(query, limit=5)
        card_results = self._repository.search_concept_cards(query, limit=3)
        top_card_score = card_results[0].score if card_results else None
        top_raw_score = raw_results[0].score if raw_results else None
        candidate_cards = [card.title for card in card_results]
        raw_candidate_sections = [section.citation for section in raw_results]

        contributing_cards: list[ConceptCardSearchResult] = []
        supported_cards: list[ConceptCardSearchResult] = []
        card_support_sections: list[RawSectionSearchResult] = []
        if card_results:
            supported_cards = filter_supported_cards(query, card_results)
            raw_sources = _deduplicate_citations(
                citation for card in supported_cards for citation in card.raw_sources
            )
            card_support_sections = _select_card_support_sections(
                citations=raw_sources,
                ranked_results=raw_results,
                repository=self._repository,
            )
            if card_support_sections:
                card_evidence = select_raw_evidence(
                    query=query,
                    results=card_support_sections,
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
                        decision_reason="card_evidence_sufficient",
                        candidate_cards=candidate_cards,
                        supported_card_titles=[card.title for card in supported_cards],
                        card_support_sections=[section.citation for section in card_support_sections],
                        raw_candidate_sections=raw_candidate_sections,
                        latency_ms=_elapsed_ms(started_at),
                    )
                contributing_cards = supported_cards

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
            self._log_query(
                query,
                response,
                top_card_score=top_card_score,
                top_raw_score=top_raw_score,
                decision_reason="raw_evidence_insufficient",
                candidate_cards=candidate_cards,
                supported_cards=[card.title for card in supported_cards],
                card_support_sections=[section.citation for section in card_support_sections],
                raw_candidate_sections=raw_candidate_sections,
                raw_evidence_sections=[section.citation for section in raw_evidence.sections],
                latency_ms=_elapsed_ms(started_at),
            )
            return response

        return self._build_raw_response(
            query=query,
            raw_evidence_sections=raw_evidence.sections,
            supported_cards=contributing_cards,
            top_card_score=top_card_score,
            strongest_evidence_score=raw_evidence.strongest_score,
            decision_reason=(
                "raw_evidence_sufficient_after_card_fallback"
                if contributing_cards
                else "raw_evidence_sufficient"
            ),
            candidate_cards=candidate_cards,
            supported_card_titles=[card.title for card in supported_cards],
            card_support_sections=[section.citation for section in card_support_sections],
            raw_candidate_sections=raw_candidate_sections,
            latency_ms=_elapsed_ms(started_at),
        )

    def _build_card_response(
        self,
        *,
        query: str,
        supported_cards: list[ConceptCardSearchResult],
        card_evidence_sections: list[RawSectionSearchResult],
        top_card_score: float | None,
        strongest_evidence_score: float,
        decision_reason: str,
        candidate_cards: list[str],
        supported_card_titles: list[str],
        card_support_sections: list[str],
        raw_candidate_sections: list[str],
        latency_ms: int,
    ) -> dict:
        prompt = build_grounded_answer_prompt(
            query=query,
            sections=card_evidence_sections,
            cards=supported_cards,
        )
        generation = self._answer_generator.generate(prompt)
        grounded_answer = parse_grounded_answer_response(generation.payload)
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
        self._log_query(
            query,
            response,
            top_card_score=top_card_score,
            top_raw_score=strongest_evidence_score,
            decision_reason=decision_reason if ok else "generator_returned_cannot_confirm_from_cards",
            candidate_cards=candidate_cards,
            supported_cards=supported_card_titles,
            card_support_sections=card_support_sections,
            raw_candidate_sections=raw_candidate_sections,
            raw_evidence_sections=[section.citation for section in card_evidence_sections],
            latency_ms=latency_ms,
            input_tokens=generation.input_tokens,
            output_tokens=generation.output_tokens,
        )
        return response

    def _build_raw_response(
        self,
        *,
        query: str,
        raw_evidence_sections: list[RawSectionSearchResult],
        supported_cards: list[ConceptCardSearchResult],
        top_card_score: float | None,
        strongest_evidence_score: float,
        decision_reason: str,
        candidate_cards: list[str],
        supported_card_titles: list[str],
        card_support_sections: list[str],
        raw_candidate_sections: list[str],
        latency_ms: int,
    ) -> dict:
        citations = [section.citation for section in raw_evidence_sections]
        prompt = build_grounded_answer_prompt(
            query=query,
            sections=raw_evidence_sections,
            cards=supported_cards or None,
        )
        generation = self._answer_generator.generate(prompt)
        grounded_answer = parse_grounded_answer_response(generation.payload)
        ok = grounded_answer.status == "ok"
        response_citations = [c for c in grounded_answer.citations if c in citations] if ok else []
        if not ok:
            mode = "none"
            used_cards: list[str] = []
        elif supported_cards:
            mode = "cards_plus_raw"
            used_cards = [card.title for card in supported_cards]
        else:
            mode = "raw"
            used_cards = []
        response = {
            "status": grounded_answer.status,
            "retrieval_mode": mode,
            "answer": grounded_answer.answer,
            "citations": response_citations,
            "used_cards": used_cards,
            "used_raw_sections": response_citations,
            "message": "Answer generated from raw section retrieval.",
        }
        self._log_query(
            query,
            response,
            top_card_score=top_card_score,
            top_raw_score=strongest_evidence_score,
            decision_reason=decision_reason if ok else "generator_returned_cannot_confirm_from_raw",
            candidate_cards=candidate_cards,
            supported_cards=supported_card_titles,
            card_support_sections=card_support_sections,
            raw_candidate_sections=raw_candidate_sections,
            raw_evidence_sections=citations,
            latency_ms=latency_ms,
            input_tokens=generation.input_tokens,
            output_tokens=generation.output_tokens,
        )
        return response

    def _log_query(
        self,
        query: str,
        response: dict,
        *,
        top_card_score: float | None = None,
        top_raw_score: float | None = None,
        decision_reason: str = "",
        candidate_cards: list[str] | None = None,
        supported_cards: list[str] | None = None,
        card_support_sections: list[str] | None = None,
        raw_candidate_sections: list[str] | None = None,
        raw_evidence_sections: list[str] | None = None,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
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
                decision_reason=decision_reason,
                candidate_cards=candidate_cards or [],
                supported_cards=supported_cards or [],
                card_support_sections=card_support_sections or [],
                raw_candidate_sections=raw_candidate_sections or [],
                raw_evidence_sections=raw_evidence_sections or [],
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
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


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
