import json
from pathlib import Path

from app.domain.concept_card_builder import GeneratedCardContent
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


def test_indexing_service_skips_unchanged_documents_and_deactivates_deleted_ones(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )
    (docs_dir / "shipping_faq.md").write_text(
        "# Shipping FAQ\nStandard shipping takes 3 business days.\n",
        encoding="utf-8",
    )
    service = IndexingService(
        docs_dir=docs_dir,
        manifest_path=kb_dir / "index.json",
        database_path=kb_dir / "knowledge_base.db",
        max_chunk_chars=1_000,
    )

    first = service.rebuild_index()
    (docs_dir / "shipping_faq.md").unlink()
    second = service.rebuild_index()

    from app.db.raw_index_repository import RawIndexRepository

    repository = RawIndexRepository(kb_dir / "knowledge_base.db")
    active_paths = [record.path for record in repository.list_active_documents()]

    assert first["files_indexed"] == 2
    assert second["files_indexed"] == 0
    assert second["deleted_documents"] == 1
    assert second["unchanged_documents"] == 1
    assert active_paths == ["docs/refund_policy.md"]


def test_indexing_service_generates_concept_cards_during_rebuild(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Timeline\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )
    service = IndexingService(
        docs_dir=docs_dir,
        manifest_path=kb_dir / "index.json",
        database_path=kb_dir / "knowledge_base.db",
        max_chunk_chars=1_000,
    )

    service.rebuild_index()

    from app.db.raw_index_repository import RawIndexRepository

    repository = RawIndexRepository(kb_dir / "knowledge_base.db")
    cards = repository.search_concept_cards("refunds timeline", limit=3)

    assert len(cards) == 1
    assert cards[0].title == "Refund Timeline"


def test_indexing_service_replaces_stale_concept_cards_on_rebuild(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    document_path = docs_dir / "refund_policy.md"
    document_path.write_text(
        "# Refund Timeline\nRefunds are processed within 5 business days.\n\n## Eligibility\nOnly unused items are eligible for refunds.\n",
        encoding="utf-8",
    )
    service = IndexingService(
        docs_dir=docs_dir,
        manifest_path=kb_dir / "index.json",
        database_path=kb_dir / "knowledge_base.db",
        max_chunk_chars=1_000,
    )

    service.rebuild_index()
    document_path.write_text(
        "# Refund Timeline\nRefunds are processed within 7 business days.\n",
        encoding="utf-8",
    )
    service.rebuild_index()

    from app.db.raw_index_repository import RawIndexRepository

    repository = RawIndexRepository(kb_dir / "knowledge_base.db")
    timeline_cards = repository.search_concept_cards("refunds timeline", limit=3)
    eligibility_cards = repository.search_concept_cards("eligibility", limit=3)

    assert len(timeline_cards) == 1
    assert timeline_cards[0].summary == "Refunds are processed within 7 business days."
    assert eligibility_cards == []


def test_indexing_service_does_not_call_card_generator_for_unchanged_documents(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Timeline\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )

    class CountingGenerator:
        def __init__(self) -> None:
            self.call_count = 0

        def generate(self, title: str, sections: list[str]) -> GeneratedCardContent:  # noqa: ARG002
            self.call_count += 1
            return GeneratedCardContent(summary="summary", key_points=["point"])

    generator = CountingGenerator()
    service = IndexingService(
        docs_dir=docs_dir,
        manifest_path=kb_dir / "index.json",
        database_path=kb_dir / "knowledge_base.db",
        max_chunk_chars=1_000,
        card_generator=generator,
    )

    service.rebuild_index()
    first_count = generator.call_count

    service.rebuild_index()

    assert first_count == 1
    assert generator.call_count == 1
