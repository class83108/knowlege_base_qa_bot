from __future__ import annotations

from typing import Callable

from app.db.raw_index_repository import ConceptCardRecord, ConceptCardSearchResult
from app.domain.concept_card_builder import CardGenerator, _make_card, group_sections_by_heading
from app.domain.markdown_parser import ParsedDocument
from app.domain.retrieval_policy import CARD_SCORE_THRESHOLD


def maintain_concept_cards(
    documents: list[ParsedDocument],
    *,
    search_cards: Callable[[str, int], list[ConceptCardSearchResult]],
    card_generator: CardGenerator | None = None,
    candidate_limit: int = 3,
) -> list[ConceptCardRecord]:
    grouped = group_sections_by_heading(documents)
    result = []
    for title, (contents, citations) in grouped.items():
        candidates = [
            c for c in search_cards(title, candidate_limit)
            if c.score <= CARD_SCORE_THRESHOLD
        ]
        if candidates:
            best = candidates[0]
            card = _make_card(best.title, contents, citations, card_generator)
        else:
            card = _make_card(title, contents, citations, card_generator)
        result.append(card)
    return result
