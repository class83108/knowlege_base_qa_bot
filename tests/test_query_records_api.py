from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_get_query_records_returns_empty_list_before_any_queries(tmp_path: Path) -> None:
    kb_dir = tmp_path / ".kb"
    app = create_app(
        docs_dir=tmp_path / "docs",
        kb_dir=kb_dir,
        sqlite_path=kb_dir / "knowledge_base.db",
        openai_api_key=None,
    )
    client = TestClient(app)

    response = client.get("/query-records")

    assert response.status_code == 200
    assert response.json() == []


def test_get_query_records_returns_logged_queries(tmp_path: Path) -> None:
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

    response = client.get("/query-records")

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["query_text"] == "How long do refunds take?"
    assert records[0]["status"] == "ok"
    assert records[0]["retrieval_mode"] == "cards"


def test_get_query_records_includes_scores(tmp_path: Path) -> None:
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

    response = client.get("/query-records")

    records = response.json()
    assert "top_card_score" in records[0]
    assert "top_raw_score" in records[0]
    assert records[0]["top_card_score"] is not None
    assert records[0]["top_raw_score"] is not None
    assert "decision_reason" in records[0]
    assert "candidate_cards" in records[0]
    assert "raw_evidence_sections" in records[0]
    assert "latency_ms" in records[0]
    assert "input_tokens" in records[0]
    assert "output_tokens" in records[0]
