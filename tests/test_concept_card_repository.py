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
