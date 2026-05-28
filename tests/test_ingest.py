import json
from pathlib import Path

from app.domain.ingest import ingest_markdown_directory
from app.domain.index_manifest import build_index_manifest


def test_ingest_markdown_directory_returns_sorted_documents(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "b.md").write_text("# B\nBravo\n", encoding="utf-8")
    (docs_dir / "a.md").write_text("# A\nAlpha\n", encoding="utf-8")

    documents = ingest_markdown_directory(docs_dir, max_chunk_chars=1_000)

    assert [document.path for document in documents] == [
        str(Path("docs/a.md")),
        str(Path("docs/b.md")),
    ]


def test_ingest_markdown_directory_ignores_non_markdown_files(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    (docs_dir / "policy.md").write_text("# Policy\nContent\n", encoding="utf-8")

    documents = ingest_markdown_directory(docs_dir, max_chunk_chars=1_000)

    assert len(documents) == 1
    assert documents[0].path == "docs/policy.md"


def test_ingest_markdown_directory_creates_fallback_section_for_headingless_documents(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "faq.md").write_text("Intro without heading.\n\nMore details.\n", encoding="utf-8")

    documents = ingest_markdown_directory(docs_dir, max_chunk_chars=1_000)

    assert len(documents) == 1
    assert documents[0].title == "faq"
    assert len(documents[0].sections) == 1
    assert documents[0].sections[0].heading == "faq"
    assert documents[0].sections[0].citation == "faq.md#faq"


def test_build_index_manifest_returns_serializable_index_shape(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )

    documents = ingest_markdown_directory(docs_dir, max_chunk_chars=1_000)
    manifest = build_index_manifest(documents)

    assert manifest["files_indexed"] == 1
    assert manifest["raw_sections_indexed"] == 1
    assert manifest["documents"][0]["title"] == "Refund Policy"
    assert manifest["sections"][0]["citation"] == "refund_policy.md#refund-policy"
    json.dumps(manifest)
