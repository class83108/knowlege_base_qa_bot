from __future__ import annotations

from app.db.raw_index_repository import ConceptCardRecord
from app.domain.markdown_parser import ParsedDocument


def build_concept_cards(documents: list[ParsedDocument]) -> list[ConceptCardRecord]:
    cards: list[ConceptCardRecord] = []
    seen_titles: set[str] = set()
    for document in documents:
        for section in document.sections:
            if section.heading in seen_titles:
                continue
            seen_titles.add(section.heading)
            cards.append(
                ConceptCardRecord(
                    title=section.heading,
                    summary=section.content,
                    key_points=[section.content],
                    raw_sources=[section.citation],
                )
            )
    return cards
