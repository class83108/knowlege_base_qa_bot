from __future__ import annotations

from app.db.raw_index_repository import ConceptCardSearchResult, RawSectionSearchResult
from app.domain.raw_evidence_selector import SelectedRawEvidence
from app.domain.tokenizer import tokenize

CARD_SCORE_THRESHOLD = -1e-6
EVIDENCE_SCORE_THRESHOLD = -1e-7


def filter_supported_cards(
    query: str,
    card_results: list[ConceptCardSearchResult],
) -> list[ConceptCardSearchResult]:
    return [
        card
        for card in card_results
        if card.score <= CARD_SCORE_THRESHOLD and _card_matches_query(query, card)
    ]


def is_card_evidence_sufficient(
    *,
    query: str,
    supported_cards: list[ConceptCardSearchResult],
    evidence: SelectedRawEvidence,
) -> bool:
    return bool(
        evidence.sections
        and evidence.strongest_score <= EVIDENCE_SCORE_THRESHOLD
        and _cards_have_meaningful_support(
            query=query,
            cards=supported_cards,
            sections=evidence.sections,
        )
    )


def is_raw_evidence_sufficient(evidence: SelectedRawEvidence) -> bool:
    return bool(
        evidence.sections
        and evidence.has_meaningful_overlap
        and evidence.strongest_score <= EVIDENCE_SCORE_THRESHOLD
    )


def _card_matches_query(query: str, card: ConceptCardSearchResult) -> bool:
    query_terms = tokenize(query)
    if not query_terms:
        return False
    card_terms = tokenize(card.title)
    card_terms.update(tokenize(card.summary))
    for point in card.key_points:
        card_terms.update(tokenize(point))
    return bool(query_terms & card_terms)


def _cards_have_meaningful_support(
    *,
    query: str,
    cards: list[ConceptCardSearchResult],
    sections: list[RawSectionSearchResult],
) -> bool:
    query_terms = tokenize(query)
    if not query_terms:
        return False
    support_terms: set[str] = set()
    for card in cards:
        support_terms.update(tokenize(card.title))
        support_terms.update(tokenize(card.summary))
        for point in card.key_points:
            support_terms.update(tokenize(point))
    for section in sections:
        support_terms.update(tokenize(section.content))
    return bool(query_terms & support_terms)
