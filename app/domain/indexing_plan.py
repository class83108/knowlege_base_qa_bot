from __future__ import annotations

from dataclasses import dataclass

from app.domain.markdown_parser import ParsedDocument


@dataclass(frozen=True)
class ActiveDocumentRecord:
    path: str
    content_hash: str


@dataclass(frozen=True)
class IndexingPlan:
    new_documents: list[ParsedDocument]
    changed_documents: list[ParsedDocument]
    unchanged_documents: list[ParsedDocument]
    deleted_paths: list[str]


def plan_indexing_changes(
    *,
    current_documents: list[ParsedDocument],
    active_documents: list[ActiveDocumentRecord],
) -> IndexingPlan:
    current_by_path = {document.path: document for document in current_documents}
    active_by_path = {record.path: record for record in active_documents}

    new_documents: list[ParsedDocument] = []
    changed_documents: list[ParsedDocument] = []
    unchanged_documents: list[ParsedDocument] = []

    for document in current_documents:
        active = active_by_path.get(document.path)
        if active is None:
            new_documents.append(document)
        elif active.content_hash != document.content_hash:
            changed_documents.append(document)
        else:
            unchanged_documents.append(document)

    deleted_paths = sorted(
        path for path in active_by_path.keys() if path not in current_by_path
    )
    return IndexingPlan(
        new_documents=new_documents,
        changed_documents=changed_documents,
        unchanged_documents=unchanged_documents,
        deleted_paths=deleted_paths,
    )
