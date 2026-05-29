from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.db.raw_index_repository import ConceptCardRecord
from app.domain.markdown_parser import ParsedDocument


@dataclass(frozen=True)
class GeneratedCardContent:
    summary: str
    key_points: list[str]


class CardGenerator(Protocol):
    def generate(self, title: str, sections: list[str]) -> GeneratedCardContent: ...


def build_concept_cards(
    documents: list[ParsedDocument],
    *,
    card_generator: CardGenerator | None = None,
) -> list[ConceptCardRecord]:
    grouped = _group_sections_by_heading(documents)
    return [
        _make_card(title, contents, citations, card_generator)
        for title, (contents, citations) in grouped.items()
    ]


def _group_sections_by_heading(
    documents: list[ParsedDocument],
) -> dict[str, tuple[list[str], list[str]]]:
    grouped: dict[str, tuple[list[str], list[str]]] = {}
    for document in documents:
        for section in document.sections:
            if section.heading not in grouped:
                grouped[section.heading] = ([], [])
            contents, citations = grouped[section.heading]
            if section.content not in contents:
                contents.append(section.content)
            if section.citation not in citations:
                citations.append(section.citation)
    return grouped


def _make_card(
    title: str,
    contents: list[str],
    citations: list[str],
    card_generator: CardGenerator | None,
) -> ConceptCardRecord:
    if card_generator is not None:
        generated = card_generator.generate(title=title, sections=contents)
        return ConceptCardRecord(
            title=title,
            summary=generated.summary,
            key_points=generated.key_points,
            raw_sources=citations,
        )
    return ConceptCardRecord(
        title=title,
        summary="\n\n".join(contents),
        key_points=list(contents),
        raw_sources=citations,
    )
