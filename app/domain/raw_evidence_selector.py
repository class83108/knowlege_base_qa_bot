from __future__ import annotations

from dataclasses import dataclass
import re

from app.db.raw_index_repository import RawSectionSearchResult


@dataclass(frozen=True)
class SelectedRawEvidence:
    sections: list[RawSectionSearchResult]
    total_tokens: int
    has_meaningful_overlap: bool


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
    "nearby",
    "of",
    "the",
    "to",
    "what",
    "which",
}


def select_raw_evidence(
    *,
    query: str,
    results: list[RawSectionSearchResult],
    max_sections: int,
    max_total_tokens: int,
) -> SelectedRawEvidence:
    selected_sections: list[RawSectionSearchResult] = []
    total_tokens = 0
    seen_citations: set[str] = set()

    for result in results:
        if result.citation in seen_citations:
            continue
        if len(selected_sections) >= max_sections:
            break
        if selected_sections and total_tokens + result.token_count > max_total_tokens:
            continue
        if not selected_sections and result.token_count > max_total_tokens:
            continue

        selected_sections.append(result)
        seen_citations.add(result.citation)
        total_tokens += result.token_count

    return SelectedRawEvidence(
        sections=selected_sections,
        total_tokens=total_tokens,
        has_meaningful_overlap=_has_meaningful_overlap(
            query=query,
            sections=selected_sections,
        ),
    )


def _has_meaningful_overlap(
    *,
    query: str,
    sections: list[RawSectionSearchResult],
) -> bool:
    query_terms = {
        term for term in TOKEN_PATTERN.findall(query.lower()) if term not in STOPWORDS
    }
    if not query_terms or not sections:
        return False

    content_terms = set()
    for section in sections:
        content_terms.update(TOKEN_PATTERN.findall(section.content.lower()))
    return bool(query_terms & content_terms)
