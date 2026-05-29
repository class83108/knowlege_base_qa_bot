from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_post_index_rebuilds_index_and_returns_summary(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    (docs_dir / "refund_policy.md").write_text(
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )

    app = create_app(
        docs_dir=docs_dir,
        kb_dir=kb_dir,
        sqlite_path=kb_dir / "knowledge_base.db",
    )
    client = TestClient(app)

    response = client.post("/index")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["files_indexed"] == 1
    assert response.json()["concept_cards_created"] == 1
    assert response.json()["concept_cards_updated"] == 0


def test_post_index_reports_updated_cards_on_second_call(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    kb_dir = tmp_path / ".kb"
    docs_dir.mkdir()
    doc_path = docs_dir / "refund_policy.md"
    doc_path.write_text(
        "# Refund Policy\nRefunds are processed within 5 business days.\n",
        encoding="utf-8",
    )
    app = create_app(
        docs_dir=docs_dir,
        kb_dir=kb_dir,
        sqlite_path=kb_dir / "knowledge_base.db",
    )
    client = TestClient(app)
    client.post("/index")
    doc_path.write_text(
        "# Refund Policy\nRefunds are processed within 7 business days.\n",
        encoding="utf-8",
    )

    response = client.post("/index")

    assert response.json()["concept_cards_created"] == 0
    assert response.json()["concept_cards_updated"] == 1
