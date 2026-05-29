from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.domain.markdown_parser import ParsedDocument


def build_index_manifest(documents: list[ParsedDocument]) -> dict:
    sections = [
        {
            "document_path": section.document_path,
            "heading": section.heading,
            "heading_path": section.heading_path,
            "chunk_index": section.chunk_index,
            "citation": section.citation,
            "token_count": section.token_count,
            "block_types_present": section.block_types_present,
        }
        for document in documents
        for section in document.sections
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "files_indexed": len(documents),
        "raw_sections_indexed": len(sections),
        "documents": [
            {
                "path": document.path,
                "title": document.title,
                "content_hash": document.content_hash,
            }
            for document in documents
        ],
        "sections": sections,
    }


def write_index_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
