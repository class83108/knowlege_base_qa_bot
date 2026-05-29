import json
import sqlite3
from pathlib import Path

from app.domain.index_manifest import build_index_manifest, write_index_manifest
from app.domain.markdown_parser import parse_markdown_document


def _build_document(path: str, markdown: str):
    return parse_markdown_document(
        document_path=path,
        markdown=markdown,
        max_chunk_chars=1_000,
    )


def test_write_index_manifest_persists_json_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / ".kb" / "index.json"
    document = _build_document(
        "docs/refund_policy.md",
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
    )
    manifest = build_index_manifest([document])

    write_index_manifest(manifest_path, manifest)

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["files_indexed"] == 1
    assert payload["sections"][0]["citation"] == "refund_policy.md#refund-policy"


def test_initialize_database_creates_raw_index_schema(tmp_path: Path) -> None:
    from app.db.session import initialize_database

    database_path = tmp_path / ".kb" / "knowledge_base.db"

    initialize_database(database_path)

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
