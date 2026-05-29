from app.db.raw_index_repository import RawSectionSearchResult
from app.domain.raw_evidence_selector import select_raw_evidence


def _result(
    *,
    citation: str,
    heading_path: str,
    content: str,
    token_count: int,
    score: float = -0.5,
) -> RawSectionSearchResult:
    return RawSectionSearchResult(
        document_path="docs/example.md",
        heading=heading_path.split(" > ")[-1],
        heading_path=heading_path,
        chunk_index=0,
        content=content,
        citation=citation,
        token_count=token_count,
        block_types_present=["paragraph"],
        score=score,
    )


def test_select_raw_evidence_deduplicates_by_citation() -> None:
    selected = select_raw_evidence(
        query="refunds timeline",
        results=[
            _result(
                citation="refund_policy.md#refund-timeline",
                heading_path="Refund Policy > Refund Timeline",
                content="Refunds are processed within 5 business days.",
                token_count=7,
            ),
            _result(
                citation="refund_policy.md#refund-timeline",
                heading_path="Refund Policy > Refund Timeline",
                content="Refunds are processed within 5 business days and may vary.",
                token_count=10,
            ),
        ],
        max_sections=3,
        max_total_tokens=50,
    )

    assert [item.citation for item in selected.sections] == [
        "refund_policy.md#refund-timeline"
    ]


def test_select_raw_evidence_respects_token_budget() -> None:
    selected = select_raw_evidence(
        query="refunds policy",
        results=[
            _result(
                citation="refund_policy.md#refund-timeline",
                heading_path="Refund Policy > Refund Timeline",
                content="Refunds are processed within 5 business days.",
                token_count=7,
            ),
            _result(
                citation="refund_policy.md#eligibility",
                heading_path="Refund Policy > Eligibility",
                content="Only unused items are eligible for refunds.",
                token_count=7,
            ),
            _result(
                citation="refund_policy.md#exceptions",
                heading_path="Refund Policy > Exceptions",
                content="Clearance items are final sale and not refundable.",
                token_count=9,
            ),
        ],
        max_sections=5,
        max_total_tokens=14,
    )

    assert [item.citation for item in selected.sections] == [
        "refund_policy.md#refund-timeline",
        "refund_policy.md#eligibility",
    ]
    assert selected.total_tokens == 14


def test_select_raw_evidence_limits_number_of_sections() -> None:
    selected = select_raw_evidence(
        query="refunds policy",
        results=[
            _result(
                citation="refund_policy.md#refund-timeline",
                heading_path="Refund Policy > Refund Timeline",
                content="Refunds are processed within 5 business days.",
                token_count=7,
            ),
            _result(
                citation="refund_policy.md#eligibility",
                heading_path="Refund Policy > Eligibility",
                content="Only unused items are eligible for refunds.",
                token_count=7,
            ),
            _result(
                citation="refund_policy.md#exceptions",
                heading_path="Refund Policy > Exceptions",
                content="Clearance items are final sale and not refundable.",
                token_count=9,
            ),
        ],
        max_sections=2,
        max_total_tokens=50,
    )

    assert len(selected.sections) == 2


def test_select_raw_evidence_tracks_meaningful_overlap() -> None:
    selected = select_raw_evidence(
        query="Which restaurants are nearby?",
        results=[
            _result(
                citation="refund_policy.md#refund-timeline",
                heading_path="Refund Policy > Refund Timeline",
                content="Refunds are processed within 5 business days.",
                token_count=7,
            ),
        ],
        max_sections=3,
        max_total_tokens=50,
    )

    assert selected.has_meaningful_overlap is False
