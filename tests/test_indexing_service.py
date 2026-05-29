import json
from pathlib import Path

from app.services.indexing import IndexingService


def test_indexing_service_rebuilds_raw_index_and_manifest(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )

    service = IndexingService(
        docs_dir=docs_dir,
        manifest_path=kb_dir / "index.json",
        database_path=kb_dir / "knowledge_base.db",
        max_chunk_chars=1_000,
    )

    result = service.rebuild_index()

    assert result["status"] == "ok"
    assert result["files_indexed"] == 1
    assert result["raw_sections_indexed"] == 1
    assert json.loads((kb_dir / "index.json").read_text(encoding="utf-8"))["files_indexed"] == 1

