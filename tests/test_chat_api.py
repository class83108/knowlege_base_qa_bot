from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_post_chat_returns_not_indexed_before_indexing(tmp_path: Path) -> None:
    kb_dir = tmp_path / ".kb"
    app = create_app(
        docs_dir=tmp_path / "docs",
        kb_dir=kb_dir,
        sqlite_path=kb_dir / "knowledge_base.db",
        openai_api_key=None,
    )
    client = TestClient(app)

    response = client.post("/chat", json={"query": "How long do refunds take?"})

    assert response.status_code == 200
    assert response.json()["status"] == "not_indexed"
    assert response.json()["retrieval_mode"] == "none"


def test_post_chat_returns_grounded_raw_answer_after_indexing(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Timeline\nRefunds are processed within 5 business days.\n\n## Eligibility\nOnly unused items are eligible for refunds.\n",
        encoding="utf-8",
    )
    app = create_app(
        docs_dir=docs_dir,
        kb_dir=kb_dir,
        sqlite_path=kb_dir / "knowledge_base.db",
        openai_api_key=None,
    )
    client = TestClient(app)
    client.post("/index")

    response = client.post(
        "/chat",
        json={"query": "What is the refund timeline?"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["retrieval_mode"] == "cards_plus_raw"
    assert "5 business days" in response.json()["answer"]
    assert response.json()["used_cards"] == ["Refund Timeline"]
    assert response.json()["citations"] == ["refund_policy.md#refund-timeline"]
    assert response.json()["used_raw_sections"] == ["refund_policy.md#refund-timeline"]


def test_post_chat_returns_cannot_confirm_for_weak_or_missing_matches(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Timeline\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )
    app = create_app(
        docs_dir=docs_dir,
        kb_dir=kb_dir,
        sqlite_path=kb_dir / "knowledge_base.db",
        openai_api_key=None,
    )
    client = TestClient(app)
    client.post("/index")

    response = client.post("/chat", json={"query": "Which restaurants are nearby?"})

    assert response.status_code == 200
    assert response.json()["status"] == "cannot_confirm"
    assert response.json()["retrieval_mode"] == "none"


def test_post_chat_logs_query_record(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Timeline\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )
    app = create_app(
        docs_dir=docs_dir,
        kb_dir=kb_dir,
        sqlite_path=kb_dir / "knowledge_base.db",
        openai_api_key=None,
    )
    client = TestClient(app)
    client.post("/index")

    client.post("/chat", json={"query": "How long do refunds take?"})

    from app.db.raw_index_repository import RawIndexRepository

    records = RawIndexRepository(kb_dir / "knowledge_base.db").list_query_records()

    assert len(records) == 1
    assert records[0].status == "ok"
    assert records[0].retrieval_mode == "cards_plus_raw"
    assert records[0].top_card_score is not None
    assert records[0].top_raw_score is not None
