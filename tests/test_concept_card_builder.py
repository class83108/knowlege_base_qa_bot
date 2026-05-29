from app.domain.concept_card_builder import build_concept_cards
from app.domain.markdown_parser import parse_markdown_document


def test_build_concept_cards_creates_one_card_per_section() -> None:
    document = parse_markdown_document(
        document_path="docs/refund_policy.md",
        markdown="# Refund Timeline\nRefunds are processed within 5 business days.\n\n## Eligibility\nOnly unused items are eligible for refunds.\n",
        max_chunk_chars=1_000,
    )

    cards = build_concept_cards([document])

    assert [card.title for card in cards] == ["Refund Timeline", "Eligibility"]
    assert cards[0].raw_sources == ["refund_policy.md#refund-timeline"]
    assert cards[1].raw_sources == ["refund_policy.md#eligibility"]
