from __future__ import annotations

from pathlib import Path
import re

from app.db.raw_index_repository import (
    ConceptCardSearchResult,
    QueryRecord,
    RawIndexRepository,
    RawSectionSearchResult,
)
from app.domain.prompt_builder import build_grounded_answer_prompt
from app.domain.raw_evidence_selector import select_raw_evidence
from app.services.answer_generation import (
    AnswerGenerator,
    EchoEvidenceGenerator,
    parse_grounded_answer_response,
)

MIN_CARD_SCORE = -1e-6
MIN_RAW_SCORE = -1e-7


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
            supported_cards = [
                card
                for card in card_results
                if card.score <= MIN_CARD_SCORE and _card_matches_query(query, card)
            ]
            raw_sources = _deduplicate_citations(
                citation
                for card in supported_cards
                for citation in card.raw_sources
            )
            raw_sections = _select_card_support_sections(
                citations=raw_sources,
                ranked_results=raw_results,
                repository=self._repository,
            )
            if raw_sections:
                card_evidence = select_raw_evidence(
                    query=query,
                    results=raw_sections,
                    max_sections=3,
                    max_total_tokens=200,
                )
                if (
                    card_evidence.sections
                    and card_evidence.strongest_score <= MIN_RAW_SCORE
                    and _cards_have_meaningful_support(
                        query=query,
                        cards=supported_cards,
                        sections=card_evidence.sections,
                    )
                ):
                    prompt = build_grounded_answer_prompt(
                        query=query,
                        sections=card_evidence.sections,
                    )
                    grounded_answer = parse_grounded_answer_response(
                        self._answer_generator.generate(prompt)
                    )
                    allowed_citations = [
                        section.citation for section in card_evidence.sections
                    ]
                    response_citations = [
                        citation
                        for citation in grounded_answer.citations
                        if citation in allowed_citations
                    ]
                    response = {
                        "status": grounded_answer.status,
                        "retrieval_mode": (
                            "cards_plus_raw"
                            if grounded_answer.status == "ok"
                            else "none"
                        ),
                        "answer": grounded_answer.answer,
                        "citations": response_citations,
                        "used_cards": (
                            _used_card_titles(
                                cards=supported_cards,
                                citations=response_citations,
                            )
                            if grounded_answer.status == "ok"
                            else []
                        ),
                        "used_raw_sections": (
                            response_citations
                            if grounded_answer.status == "ok"
                            else []
                        ),
                        "message": "Answer generated from concept card retrieval with raw support.",
                    }
                    self._log_query(
                        query,
                        response,
                        top_card_score=top_card_score,
                        top_raw_score=card_evidence.strongest_score,
                    )
                    return response

        evidence = select_raw_evidence(
            query=query,
            results=raw_results,
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
            self._log_query(
                query,
                response,
                top_card_score=top_card_score,
                top_raw_score=top_raw_score,
            )
            return response

        if (
            not evidence.has_meaningful_overlap
            or evidence.strongest_score > MIN_RAW_SCORE
        ):
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
            )
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
        self._log_query(
            query,
            response,
            top_card_score=top_card_score,
            top_raw_score=evidence.strongest_score,
        )
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


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "are",
    "do",
    "does",
    "how",
    "i",
    "is",
    "long",
    "of",
    "take",
    "the",
    "to",
    "what",
    "which",
}
def _cards_have_meaningful_support(
    *,
    query: str,
    cards: list[ConceptCardSearchResult],
    sections: list[RawSectionSearchResult],
) -> bool:
    query_terms = {
        term for term in TOKEN_PATTERN.findall(query.lower()) if term not in STOPWORDS
    }
    if not query_terms:
        return False

    support_terms = set()
    for card in cards:
        support_terms.update(TOKEN_PATTERN.findall(card.title.lower()))
        support_terms.update(TOKEN_PATTERN.findall(card.summary.lower()))
        for point in card.key_points:
            support_terms.update(TOKEN_PATTERN.findall(point.lower()))
    for section in sections:
        support_terms.update(TOKEN_PATTERN.findall(section.content.lower()))
    return bool(query_terms & support_terms)


def _card_matches_query(query: str, card: ConceptCardSearchResult) -> bool:
    query_terms = {
        term for term in TOKEN_PATTERN.findall(query.lower()) if term not in STOPWORDS
    }
    if not query_terms:
        return False

    card_terms = set(TOKEN_PATTERN.findall(card.title.lower()))
    card_terms.update(TOKEN_PATTERN.findall(card.summary.lower()))
    for point in card.key_points:
        card_terms.update(TOKEN_PATTERN.findall(point.lower()))
    return query_terms.issubset(card_terms)


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
    missing_citations = [
        citation for citation in citations if citation not in ranked_by_citation
    ]
    fallback_sections = repository.get_raw_sections_by_citations(missing_citations)
    fallback_by_citation = {
        section.citation: section for section in fallback_sections
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
    return [
        card.title
        for card in cards
        if citation_set.intersection(card.raw_sources)
    ]
