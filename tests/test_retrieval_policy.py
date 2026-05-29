from app.db.raw_index_repository import ConceptCardSearchResult, RawSectionSearchResult
from app.domain.raw_evidence_selector import SelectedRawEvidence
from app.domain.retrieval_policy import filter_supported_cards, is_card_evidence_sufficient, is_raw_evidence_sufficient


def _card(title: str, summary: str, key_points: list[str], score: float) -> ConceptCardSearchResult:
    return ConceptCardSearchResult(
        title=title,
        summary=summary,
        key_points=key_points,
        raw_sources=["doc.md#section"],
        score=score,
    )


def _section(content: str, score: float) -> RawSectionSearchResult:
    return RawSectionSearchResult(
        document_path="doc.md",
        heading="Section",
        heading_path="Doc > Section",
        chunk_index=0,
        content=content,
        citation="doc.md#section",
        token_count=len(content.split()),
        block_types_present=["paragraph"],
        score=score,
    )


def _evidence(sections: list[RawSectionSearchResult], *, has_overlap: bool) -> SelectedRawEvidence:
    return SelectedRawEvidence(
        sections=sections,
        total_tokens=sum(s.token_count for s in sections),
        has_meaningful_overlap=has_overlap,
        strongest_score=min((s.score for s in sections), default=0.0),
    )


# --- filter_supported_cards ---

def test_filter_supported_cards_includes_card_with_strong_score_and_matching_terms() -> None:
    cards = [_card("Refund Timeline", "Refunds take 5 days.", ["5 days"], score=-0.5)]

    result = filter_supported_cards("refund timeline", cards)

    assert len(result) == 1
    assert result[0].title == "Refund Timeline"


def test_filter_supported_cards_excludes_card_with_score_too_close_to_zero() -> None:
    cards = [_card("Refund Timeline", "Refunds take 5 days.", ["5 days"], score=-0.0000001)]

    result = filter_supported_cards("refund timeline", cards)

    assert result == []


def test_filter_supported_cards_excludes_card_whose_terms_do_not_overlap_query() -> None:
    cards = [_card("Shipping Policy", "Ships in 3 days.", ["3 days"], score=-0.5)]

    result = filter_supported_cards("refund timeline", cards)

    assert result == []


# --- is_card_evidence_sufficient ---

def test_is_card_evidence_sufficient_when_sections_strong_and_meaningful() -> None:
    cards = [_card("Refund Timeline", "Refunds take 5 days.", ["5 days"], score=-0.5)]
    sections = [_section("Refunds are processed within 5 business days.", score=-0.5)]
    evidence = _evidence(sections, has_overlap=True)

    assert is_card_evidence_sufficient(query="refund timeline", supported_cards=cards, evidence=evidence)


def test_is_card_evidence_insufficient_when_no_sections() -> None:
    cards = [_card("Refund Timeline", "Refunds take 5 days.", ["5 days"], score=-0.5)]
    evidence = _evidence([], has_overlap=False)

    assert not is_card_evidence_sufficient(query="refund timeline", supported_cards=cards, evidence=evidence)


def test_is_card_evidence_insufficient_when_score_too_weak() -> None:
    cards = [_card("Refund Timeline", "Refunds take 5 days.", ["5 days"], score=-0.5)]
    sections = [_section("Refunds are processed within 5 business days.", score=-0.00000001)]
    evidence = _evidence(sections, has_overlap=True)

    assert not is_card_evidence_sufficient(query="refund timeline", supported_cards=cards, evidence=evidence)


def test_is_card_evidence_insufficient_when_query_terms_absent_from_support() -> None:
    cards = [_card("Refund Timeline", "Refunds take 5 days.", ["5 days"], score=-0.5)]
    sections = [_section("Shipping costs apply to all orders.", score=-0.5)]
    evidence = _evidence(sections, has_overlap=True)

    assert not is_card_evidence_sufficient(query="restaurant nearby", supported_cards=cards, evidence=evidence)


# --- is_raw_evidence_sufficient ---

def test_is_raw_evidence_sufficient_when_overlap_and_strong_score() -> None:
    sections = [_section("Refunds are processed within 5 business days.", score=-0.5)]
    evidence = _evidence(sections, has_overlap=True)

    assert is_raw_evidence_sufficient(evidence)


def test_is_raw_evidence_insufficient_when_no_overlap() -> None:
    sections = [_section("Refunds are processed within 5 business days.", score=-0.5)]
    evidence = _evidence(sections, has_overlap=False)

    assert not is_raw_evidence_sufficient(evidence)


def test_is_raw_evidence_insufficient_when_no_sections() -> None:
    evidence = _evidence([], has_overlap=False)

    assert not is_raw_evidence_sufficient(evidence)


def test_is_raw_evidence_insufficient_when_score_too_weak() -> None:
    sections = [_section("Refunds are processed within 5 business days.", score=-0.00000001)]
    evidence = _evidence(sections, has_overlap=True)

    assert not is_raw_evidence_sufficient(evidence)
