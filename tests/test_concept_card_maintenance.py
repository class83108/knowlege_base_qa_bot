from app.db.raw_index_repository import ConceptCardSearchResult
from app.domain.concept_card_builder import GeneratedCardContent
from app.domain.concept_card_maintenance import maintain_concept_cards
from app.domain.markdown_parser import parse_markdown_document


class FakeCardGenerator:
    def __init__(self, summary: str, key_points: list[str]) -> None:
        self.summary = summary
        self.key_points = key_points
        self.calls: list[dict] = []

    def generate(self, title: str, sections: list[str]) -> GeneratedCardContent:
        self.calls.append({"title": title, "sections": list(sections)})
        return GeneratedCardContent(summary=self.summary, key_points=self.key_points)


class FakeCardGeneratorWithRelations:
    def __init__(self, *, related_cards: list[str]) -> None:
        self.related_cards = related_cards

    def generate(self, title: str, sections: list[str]) -> GeneratedCardContent:  # noqa: ARG002
        return GeneratedCardContent(
            summary=f"{title} summary",
            key_points=[f"{title} point"],
            related_cards=self.related_cards,
        )


def _doc(path: str, markdown: str):
    return parse_markdown_document(
        document_path=path,
        markdown=markdown,
        max_chunk_chars=1_000,
    )


def test_creates_new_card_when_no_candidates_found() -> None:
    doc = _doc("docs/refund.md", "# Refund Timeline\nRefunds take 5 days.\n")
    generator = FakeCardGenerator(summary="Refunds take 5 days.", key_points=["5 days"])

    cards = maintain_concept_cards(
        [doc],
        search_cards=lambda query, limit: [],
        card_generator=generator,
    )

    assert len(cards) == 1
    assert cards[0].title == "Refund Timeline"
    assert cards[0].raw_sources == ["refund.md#refund-timeline"]


def test_creates_new_card_when_all_candidates_are_weak() -> None:
    doc = _doc("docs/refund.md", "# Refund Timeline\nRefunds take 5 days.\n")
    generator = FakeCardGenerator(summary="Refunds take 5 days.", key_points=["5 days"])
    weak = ConceptCardSearchResult(
        title="Refund Timeline",
        summary="Old summary",
        key_points=["old point"],
        raw_sources=["old.md#refund-timeline"],
        score=0.0,  # above CARD_SCORE_THRESHOLD (-1e-6), treated as no match
    )

    cards = maintain_concept_cards(
        [doc],
        search_cards=lambda query, limit: [weak],
        card_generator=generator,
    )

    assert len(cards) == 1
    assert cards[0].raw_sources == ["refund.md#refund-timeline"]


def test_uses_existing_card_title_when_updating() -> None:
    doc = _doc("docs/refund_v2.md", "# Refund Policy\nRefunds now take 7 days.\n")
    generator = FakeCardGenerator(summary="Updated: 7 days", key_points=["7 days"])
    existing = ConceptCardSearchResult(
        title="Refund Timeline",
        summary="Refunds take 5 days.",
        key_points=["5 days"],
        raw_sources=["refund.md#refund-timeline"],
        score=-0.5,
    )

    cards = maintain_concept_cards(
        [doc],
        search_cards=lambda query, limit: [existing],
        card_generator=generator,
    )

    assert len(cards) == 1
    assert cards[0].title == "Refund Timeline"


def test_uses_new_section_citations_when_updating_existing_card() -> None:
    doc = _doc("docs/refund_v2.md", "# Refund Timeline\nRefunds now take 7 days.\n")
    generator = FakeCardGenerator(summary="Updated: 7 days", key_points=["7 days"])
    existing = ConceptCardSearchResult(
        title="Refund Timeline",
        summary="Refunds take 5 days.",
        key_points=["5 days"],
        raw_sources=["refund.md#refund-timeline"],
        score=-0.5,
    )

    cards = maintain_concept_cards(
        [doc],
        search_cards=lambda query, limit: [existing],
        card_generator=generator,
    )

    assert cards[0].raw_sources == ["refund_v2.md#refund-timeline"]


def test_passes_new_section_content_to_generator_when_updating() -> None:
    doc = _doc("docs/refund_v2.md", "# Refund Timeline\nRefunds now take 7 days.\n")
    generator = FakeCardGenerator(summary="Updated", key_points=["updated"])
    existing = ConceptCardSearchResult(
        title="Refund Timeline",
        summary="Refunds take 5 days.",
        key_points=["5 days"],
        raw_sources=["refund.md#refund-timeline"],
        score=-0.5,
    )

    maintain_concept_cards(
        [doc],
        search_cards=lambda query, limit: [existing],
        card_generator=generator,
    )

    assert len(generator.calls) == 1
    sections = generator.calls[0]["sections"]
    assert "Refunds now take 7 days." in sections
    assert "5 days" not in sections


def test_searches_cards_using_section_heading_as_query() -> None:
    doc = _doc("docs/refund.md", "# Refund Timeline\nRefunds take 5 days.\n")
    queries: list[str] = []

    def search_cards(query: str, limit: int):
        queries.append(query)
        return []

    maintain_concept_cards([doc], search_cards=search_cards)

    assert len(queries) == 1
    assert queries[0] == "Refund Timeline"


def test_creates_card_without_llm_when_no_generator() -> None:
    doc = _doc("docs/refund.md", "# Refund Timeline\nRefunds take 5 days.\n")

    cards = maintain_concept_cards(
        [doc],
        search_cards=lambda query, limit: [],
    )

    assert len(cards) == 1
    assert "Refunds take 5 days." in cards[0].summary


def test_filters_related_cards_to_known_titles() -> None:
    docs = [
        _doc("docs/refund.md", "# Refund Timeline\nRefunds take 5 days.\n"),
        _doc("docs/shipping.md", "# Expedited Shipping\nShipping takes 2 days.\n"),
    ]
    generator = FakeCardGeneratorWithRelations(
        related_cards=[
            "Expedited Shipping",
            "Order Returns",
            "Refund Timeline",
        ]
    )

    cards = maintain_concept_cards(
        docs,
        search_cards=lambda query, limit: [],
        card_generator=generator,
    )

    refund_card = next(card for card in cards if card.title == "Refund Timeline")
    shipping_card = next(card for card in cards if card.title == "Expedited Shipping")

    assert refund_card.related_cards == ["Expedited Shipping"]
    assert shipping_card.related_cards == ["Refund Timeline"]
