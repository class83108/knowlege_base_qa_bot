from pathlib import Path


def test_initialize_schema_creates_concept_card_tables(tmp_path: Path) -> None:
    from app.db.raw_index_repository import initialize_raw_index_schema

    database_path = tmp_path / "kb.db"
    initialize_raw_index_schema(database_path)

    import sqlite3

    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
    finally:
        connection.close()

    assert "concept_card" in tables
    assert "concept_card_source" in tables
    assert "concept_card_fts" in tables


def test_repository_can_upsert_and_search_concept_cards(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        ConceptCardRecord,
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    database_path = tmp_path / "kb.db"
    initialize_raw_index_schema(database_path)
    repository = RawIndexRepository(database_path)

    repository.upsert_concept_cards(
        [
            ConceptCardRecord(
                title="Refund Timeline",
                summary="Refunds are processed within 5 business days.",
                key_points=["Refunds take 5 business days."],
                raw_sources=["refund_policy.md#refund-timeline"],
            )
        ]
    )

    results = repository.search_concept_cards("refunds timeline", limit=3)

    assert len(results) == 1
    assert results[0].title == "Refund Timeline"
    assert results[0].raw_sources == ["refund_policy.md#refund-timeline"]
    assert isinstance(results[0].score, float)


def test_repository_replace_concept_cards_deactivates_stale_cards(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        ConceptCardRecord,
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    database_path = tmp_path / "kb.db"
    initialize_raw_index_schema(database_path)
    repository = RawIndexRepository(database_path)

    repository.replace_concept_cards(
        [
            ConceptCardRecord(
                title="Refund Timeline",
                summary="Refunds are processed within 5 business days.",
                key_points=["Refunds take 5 business days."],
                raw_sources=["refund_policy.md#refund-timeline"],
            ),
            ConceptCardRecord(
                title="Eligibility",
                summary="Only unused items are eligible for refunds.",
                key_points=["Unused items are eligible."],
                raw_sources=["refund_policy.md#eligibility"],
            ),
        ]
    )
    repository.replace_concept_cards(
        [
            ConceptCardRecord(
                title="Refund Timeline",
                summary="Refunds are processed within 7 business days.",
                key_points=["Refunds take 7 business days."],
                raw_sources=["refund_policy.md#refund-timeline"],
            )
        ]
    )

    eligibility_results = repository.search_concept_cards("eligibility", limit=3)
    timeline_results = repository.search_concept_cards("refunds timeline", limit=3)

    assert eligibility_results == []
    assert len(timeline_results) == 1
    assert timeline_results[0].summary == "Refunds are processed within 7 business days."


def test_repository_stores_and_retrieves_related_cards(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        ConceptCardRecord,
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    db_path = tmp_path / "kb.db"
    initialize_raw_index_schema(db_path)
    repo = RawIndexRepository(db_path)

    repo.upsert_concept_cards(
        [
            ConceptCardRecord(
                title="Refund Timeline",
                summary="Refunds take 5 days.",
                key_points=["5 days"],
                raw_sources=["refund_policy.md#refund-timeline"],
                related_cards=["Eligibility", "Returns Policy"],
            )
        ]
    )

    results = repo.search_concept_cards("refunds", limit=3)

    assert len(results) == 1
    assert results[0].related_cards == ["Eligibility", "Returns Policy"]


def test_deactivate_unsupported_cards_marks_card_inactive_when_raw_section_removed(
    tmp_path: Path,
) -> None:
    from app.db.raw_index_repository import (
        ConceptCardRecord,
        RawIndexRepository,
        initialize_raw_index_schema,
    )
    from app.domain.markdown_parser import parse_markdown_document

    db_path = tmp_path / "kb.db"
    initialize_raw_index_schema(db_path)
    repo = RawIndexRepository(db_path)

    doc = parse_markdown_document(
        document_path="docs/refund.md",
        markdown="# Refund Timeline\nRefunds take 5 days.\n",
        max_chunk_chars=1_000,
    )
    repo.replace_documents([doc])
    repo.upsert_concept_cards(
        [
            ConceptCardRecord(
                title="Refund Timeline",
                summary="Refunds take 5 days.",
                key_points=["5 days"],
                raw_sources=["refund.md#refund-timeline"],
            )
        ]
    )

    repo.deactivate_deleted_paths(["docs/refund.md"])
    repo.deactivate_unsupported_cards()

    assert repo.search_concept_cards("refunds", limit=3) == []


def test_deactivate_unsupported_cards_keeps_card_active_when_some_sources_remain(
    tmp_path: Path,
) -> None:
    from app.db.raw_index_repository import (
        ConceptCardRecord,
        RawIndexRepository,
        initialize_raw_index_schema,
    )
    from app.domain.markdown_parser import parse_markdown_document

    db_path = tmp_path / "kb.db"
    initialize_raw_index_schema(db_path)
    repo = RawIndexRepository(db_path)

    doc_a = parse_markdown_document(
        document_path="docs/refund_a.md",
        markdown="# Refund Timeline\nRefunds take 5 days.\n",
        max_chunk_chars=1_000,
    )
    doc_b = parse_markdown_document(
        document_path="docs/refund_b.md",
        markdown="# Refund Timeline\nRefunds take 7 days.\n",
        max_chunk_chars=1_000,
    )
    repo.replace_documents([doc_a, doc_b])
    repo.upsert_concept_cards(
        [
            ConceptCardRecord(
                title="Refund Timeline",
                summary="Refunds take 5-7 days.",
                key_points=["5-7 days"],
                raw_sources=[
                    "refund_a.md#refund-timeline",
                    "refund_b.md#refund-timeline",
                ],
            )
        ]
    )

    repo.deactivate_deleted_paths(["docs/refund_a.md"])
    repo.deactivate_unsupported_cards()

    results = repo.search_concept_cards("refunds", limit=3)
    assert len(results) == 1
    assert results[0].title == "Refund Timeline"


def test_prune_related_cards_removes_missing_and_self_links(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        ConceptCardRecord,
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    db_path = tmp_path / "kb.db"
    initialize_raw_index_schema(db_path)
    repo = RawIndexRepository(db_path)

    repo.upsert_concept_cards(
        [
            ConceptCardRecord(
                title="Refund Timeline",
                summary="Refunds take 5 days.",
                key_points=["5 days"],
                raw_sources=["refund_policy.md#refund-timeline"],
                related_cards=["Refund Timeline", "Expedited Shipping", "Order Returns"],
            ),
            ConceptCardRecord(
                title="Expedited Shipping",
                summary="Shipping takes 2 days.",
                key_points=["2 days"],
                raw_sources=["shipping_faq.md#expedited-shipping"],
                related_cards=[],
            ),
        ]
    )

    repo.prune_related_cards()

    results = repo.search_concept_cards("refunds", limit=3)
    assert len(results) == 1
    assert results[0].related_cards == ["Expedited Shipping"]
