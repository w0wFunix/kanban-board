import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["db"] == "ok"


def test_crud():
    c = client.post("/api/cards", json={"title": "Тест"}).json()
    assert c["status"] == "todo"
    r = client.patch(f"/api/cards/{c['id']}", json={"status": "doing", "title": "Новое"})
    assert r.json()["status"] == "doing" and r.json()["title"] == "Новое"
    assert any(x["id"] == c["id"] for x in client.get("/api/cards").json())
    assert client.delete(f"/api/cards/{c['id']}").status_code == 204
    assert client.patch(f"/api/cards/{c['id']}", json={"title": "x"}).status_code == 404


def test_empty_title_rejected():
    assert client.post("/api/cards", json={"title": "  "}).status_code == 422


def test_metrics_and_stats():
    assert "app_cpu_percent" in client.get("/metrics").text
    assert len(client.get("/api/stats/hourly").json()) == 24
