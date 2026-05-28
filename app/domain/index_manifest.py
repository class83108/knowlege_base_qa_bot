from __future__ import annotations

from datetime import UTC, datetime

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
