from __future__ import annotations

from pathlib import Path

from app.domain.markdown_parser import ParsedDocument, parse_markdown_document


def ingest_markdown_directory(
    docs_dir: Path,
    *,
    max_chunk_chars: int,
) -> list[ParsedDocument]:
    documents: list[ParsedDocument] = []
    for markdown_path in sorted(docs_dir.glob("*.md")):
        markdown = markdown_path.read_text(encoding="utf-8")
        document_path = str(Path(docs_dir.name) / markdown_path.name)
        documents.append(
            parse_markdown_document(
                document_path=document_path,
                markdown=markdown,
                max_chunk_chars=max_chunk_chars,
            )
        )
    return documents
