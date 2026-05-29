from __future__ import annotations

from app.db.raw_index_repository import ConceptCardRecord
from app.domain.markdown_parser import ParsedDocument


def build_concept_cards(documents: list[ParsedDocument]) -> list[ConceptCardRecord]:
    merged_cards: dict[str, ConceptCardRecord] = {}
    for document in documents:
        for section in document.sections:
            existing = merged_cards.get(section.heading)
            if existing is None:
                merged_cards[section.heading] = ConceptCardRecord(
                    title=section.heading,
                    summary=section.content,
                    key_points=[section.content],
                    raw_sources=[section.citation],
                )
                continue

            raw_sources = _dedupe_preserve_order(existing.raw_sources + [section.citation])
            key_points = _dedupe_preserve_order(existing.key_points + [section.content])
            summary_parts = _dedupe_preserve_order(
                [existing.summary, section.content]
            )
            merged_cards[section.heading] = ConceptCardRecord(
                title=existing.title,
                summary="\n\n".join(summary_parts),
                key_points=key_points,
                raw_sources=raw_sources,
            )
    return list(merged_cards.values())


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
