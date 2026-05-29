from app.domain.concept_card_builder import (
    CardGenerator,
    GeneratedCardContent,
    build_concept_cards,
)
from app.domain.markdown_parser import parse_markdown_document


class FakeCardGenerator:
    def __init__(self, summary: str, key_points: list[str]) -> None:
        self.summary = summary
        self.key_points = key_points
        self.calls: list[dict] = []

    def generate(self, title: str, sections: list[str]) -> GeneratedCardContent:
        self.calls.append({"title": title, "sections": list(sections)})
        return GeneratedCardContent(summary=self.summary, key_points=self.key_points)


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


def test_build_concept_cards_uses_generator_for_summary() -> None:
    document = parse_markdown_document(
        document_path="docs/refund_policy.md",
        markdown="# Refund Timeline\nRefunds are processed within 5 business days.\n",
        max_chunk_chars=1_000,
    )
    generator = FakeCardGenerator(summary="LLM summary", key_points=["point"])

    cards = build_concept_cards([document], card_generator=generator)

    assert cards[0].summary == "LLM summary"


def test_build_concept_cards_uses_generator_for_key_points() -> None:
    document = parse_markdown_document(
        document_path="docs/refund_policy.md",
        markdown="# Refund Timeline\nRefunds are processed within 5 business days.\n",
        max_chunk_chars=1_000,
    )
    generator = FakeCardGenerator(summary="LLM summary", key_points=["point A", "point B"])

    cards = build_concept_cards([document], card_generator=generator)

    assert cards[0].key_points == ["point A", "point B"]


def test_build_concept_cards_passes_all_merged_sections_to_generator() -> None:
    first = parse_markdown_document(
        document_path="docs/refund_policy.md",
        markdown="# Refund Timeline\nRefunds are processed within 5 business days.\n",
        max_chunk_chars=1_000,
    )
    second = parse_markdown_document(
        document_path="docs/returns_faq.md",
        markdown="# Refund Timeline\nMost refunds complete within 5 to 7 business days.\n",
        max_chunk_chars=1_000,
    )
    generator = FakeCardGenerator(summary="merged", key_points=["merged point"])

    build_concept_cards([first, second], card_generator=generator)

    assert len(generator.calls) == 1
    assert generator.calls[0]["title"] == "Refund Timeline"
    assert "Refunds are processed within 5 business days." in generator.calls[0]["sections"]
    assert "Most refunds complete within 5 to 7 business days." in generator.calls[0]["sections"]


def test_build_concept_cards_merges_sections_with_same_heading() -> None:
    first = parse_markdown_document(
        document_path="docs/refund_policy.md",
        markdown="# Refund Timeline\nRefunds are processed within 5 business days.\n",
        max_chunk_chars=1_000,
    )
    second = parse_markdown_document(
        document_path="docs/returns_faq.md",
        markdown="# Refund Timeline\nMost refunds complete within 5 to 7 business days.\n",
        max_chunk_chars=1_000,
    )

    cards = build_concept_cards([first, second])

    assert len(cards) == 1
    assert cards[0].title == "Refund Timeline"
    assert cards[0].raw_sources == [
        "refund_policy.md#refund-timeline",
        "returns_faq.md#refund-timeline",
    ]
    assert "Refunds are processed within 5 business days." in cards[0].summary
    assert "Most refunds complete within 5 to 7 business days." in cards[0].summary
    assert cards[0].key_points == [
        "Refunds are processed within 5 business days.",
        "Most refunds complete within 5 to 7 business days.",
    ]
