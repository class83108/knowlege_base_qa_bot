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
