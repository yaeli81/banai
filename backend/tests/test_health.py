from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_api_docs_are_hidden_in_production(monkeypatch):
    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PROPOSAL_SIGNING_KEY", "production-test-key")  # required in production
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
    finally:
        get_settings.cache_clear()
