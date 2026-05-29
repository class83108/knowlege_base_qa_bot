from pathlib import Path


def test_initialize_schema_creates_query_record_table(tmp_path: Path) -> None:
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

    assert "query_record" in tables


def test_log_query_record_persists_chat_observability_fields(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        QueryRecord,
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    database_path = tmp_path / "kb.db"
    initialize_raw_index_schema(database_path)
    repository = RawIndexRepository(database_path)

    repository.log_query_record(
        QueryRecord(
            query_text="How long do refunds take?",
            status="ok",
            retrieval_mode="raw",
            answer="Refunds are processed within 5 business days.",
            citations=["refund_policy.md#refund-timeline"],
            used_cards=[],
            used_raw_sections=["refund_policy.md#refund-timeline"],
        )
    )

    records = repository.list_query_records()

    assert len(records) == 1
    assert records[0].query_text == "How long do refunds take?"
    assert records[0].status == "ok"
    assert records[0].retrieval_mode == "raw"
    assert records[0].citations == ["refund_policy.md#refund-timeline"]
