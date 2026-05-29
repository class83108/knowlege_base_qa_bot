from app.domain.indexing_plan import ActiveDocumentRecord, plan_indexing_changes
from app.domain.markdown_parser import parse_markdown_document


def _document(path: str, markdown: str):
    return parse_markdown_document(
        document_path=path,
        markdown=markdown,
        max_chunk_chars=1_000,
    )


def test_plan_indexing_changes_classifies_new_changed_unchanged_and_deleted() -> None:
    current_documents = [
        _document("docs/a.md", "# A\nsame\n"),
        _document("docs/b.md", "# B\nchanged now\n"),
        _document("docs/d.md", "# D\nnew file\n"),
    ]
    active_documents = [
        ActiveDocumentRecord(path="docs/a.md", content_hash=current_documents[0].content_hash),
        ActiveDocumentRecord(path="docs/b.md", content_hash="old-hash"),
        ActiveDocumentRecord(path="docs/c.md", content_hash="deleted-hash"),
    ]

    plan = plan_indexing_changes(
        current_documents=current_documents,
        active_documents=active_documents,
    )

    assert [document.path for document in plan.new_documents] == ["docs/d.md"]
    assert [document.path for document in plan.changed_documents] == ["docs/b.md"]
    assert [document.path for document in plan.unchanged_documents] == ["docs/a.md"]
    assert plan.deleted_paths == ["docs/c.md"]
