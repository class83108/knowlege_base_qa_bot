from __future__ import annotations

from pathlib import Path

from app.db.raw_index_repository import RawIndexRepository, initialize_raw_index_schema
from app.domain.concept_card_builder import CardGenerator
from app.domain.concept_card_maintenance import maintain_concept_cards
from app.domain.indexing_plan import (
    ActiveDocumentRecord,
    plan_indexing_changes,
)
from app.domain.index_manifest import build_index_manifest, write_index_manifest
from app.domain.ingest import ingest_markdown_directory


class IndexingService:
    def __init__(
        self,
        *,
        docs_dir: Path,
        manifest_path: Path,
        database_path: Path,
        max_chunk_chars: int,
        card_generator: CardGenerator | None = None,
    ) -> None:
        self._docs_dir = docs_dir
        self._manifest_path = manifest_path
        self._database_path = database_path
        self._max_chunk_chars = max_chunk_chars
        self._card_generator = card_generator

    def rebuild_index(self) -> dict:
        initialize_raw_index_schema(self._database_path)
        documents = ingest_markdown_directory(
            self._docs_dir,
            max_chunk_chars=self._max_chunk_chars,
        )
        repository = RawIndexRepository(self._database_path)
        plan = plan_indexing_changes(
            current_documents=documents,
            active_documents=[
                ActiveDocumentRecord(
                    path=record.path,
                    content_hash=record.content_hash,
                )
                for record in repository.list_active_documents()
            ],
        )
        repository.deactivate_deleted_paths(plan.deleted_paths)
        documents_to_replace = plan.new_documents + plan.changed_documents
        current_documents = plan.unchanged_documents + plan.new_documents + plan.changed_documents
        summary = repository.replace_documents(documents_to_replace)
        if documents_to_replace:
            repository.upsert_concept_cards(
                maintain_concept_cards(
                    documents_to_replace,
                    search_cards=lambda q, n: repository.search_concept_cards(q, limit=n),
                    card_generator=self._card_generator,
                )
            )
        repository.deactivate_unsupported_cards()
        manifest = build_index_manifest(current_documents)
        write_index_manifest(self._manifest_path, manifest)
        return {
            "status": "ok",
            "files_indexed": summary.files_indexed,
            "raw_sections_indexed": summary.raw_sections_indexed,
            "unchanged_documents": len(plan.unchanged_documents),
            "deleted_documents": len(plan.deleted_paths),
            "message": "Index rebuilt successfully.",
        }
