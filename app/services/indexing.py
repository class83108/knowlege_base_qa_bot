from __future__ import annotations

from pathlib import Path

from app.db.raw_index_repository import RawIndexRepository, initialize_raw_index_schema
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
    ) -> None:
        self._docs_dir = docs_dir
        self._manifest_path = manifest_path
        self._database_path = database_path
        self._max_chunk_chars = max_chunk_chars

    def rebuild_index(self) -> dict:
        initialize_raw_index_schema(self._database_path)
        documents = ingest_markdown_directory(
            self._docs_dir,
            max_chunk_chars=self._max_chunk_chars,
        )
        repository = RawIndexRepository(self._database_path)
        summary = repository.replace_documents(documents)
        manifest = build_index_manifest(documents)
        write_index_manifest(self._manifest_path, manifest)
        return {
            "status": "ok",
            "files_indexed": summary.files_indexed,
            "raw_sections_indexed": summary.raw_sections_indexed,
            "message": "Index rebuilt successfully.",
        }
