import sqlite3
from pathlib import Path

from app.domain.markdown_parser import parse_markdown_document


def _build_document(path: str, markdown: str):
    return parse_markdown_document(
        document_path=path,
        markdown=markdown,
        max_chunk_chars=1_000,
    )


def test_initialize_schema_creates_raw_index_tables(tmp_path: Path) -> None:
    from app.db.raw_index_repository import initialize_raw_index_schema

    database_path = tmp_path / "kb.db"

    initialize_raw_index_schema(database_path)

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

    assert "source_document" in tables
    assert "raw_section" in tables
    assert "raw_section_fts" in tables


def test_upsert_documents_persists_documents_sections_and_fts(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    database_path = tmp_path / "kb.db"
    initialize_raw_index_schema(database_path)
    repository = RawIndexRepository(database_path)
    document = _build_document(
        "docs/refund_policy.md",
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
    )

    summary = repository.replace_documents([document])
    results = repository.search_raw_sections("refunds business days", limit=5)

    assert summary.files_indexed == 1
    assert summary.raw_sections_indexed == 1
    assert len(results) == 1
    assert results[0].document_path == "docs/refund_policy.md"
    assert results[0].citation == "refund_policy.md#refund-policy"
    assert "5 business days" in results[0].content


def test_replace_documents_marks_previous_versions_inactive(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    database_path = tmp_path / "kb.db"
    initialize_raw_index_schema(database_path)
    repository = RawIndexRepository(database_path)
    first_version = _build_document(
        "docs/refund_policy.md",
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
    )
    second_version = _build_document(
        "docs/refund_policy.md",
        "# Refund Policy\nRefunds are processed within 7 business days.\n",
    )

    repository.replace_documents([first_version])
    repository.replace_documents([second_version])

    results = repository.search_raw_sections("7 business days", limit=5)
    stale_results = repository.search_raw_sections("5 business days", limit=5)

    assert len(results) == 1
    assert "7 business days" in results[0].content
    assert stale_results == []


def test_repository_lists_active_documents_and_can_deactivate_deleted_paths(tmp_path: Path) -> None:
    from app.db.raw_index_repository import (
        RawIndexRepository,
        initialize_raw_index_schema,
    )

    database_path = tmp_path / "kb.db"
    initialize_raw_index_schema(database_path)
    repository = RawIndexRepository(database_path)
    document = _build_document(
        "docs/refund_policy.md",
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
    )

    repository.replace_documents([document])

    active_before = repository.list_active_documents()
    repository.deactivate_deleted_paths(["docs/refund_policy.md"])
    active_after = repository.list_active_documents()
    results_after = repository.search_raw_sections("refunds business days", limit=5)

    assert [record.path for record in active_before] == ["docs/refund_policy.md"]
    assert active_after == []
    assert results_after == []
