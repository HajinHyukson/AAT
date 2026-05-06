from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_api_key_is_optional_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("AAT_API_KEY", raising=False)

    client = TestClient(app)

    response = client.get("/version")

    assert response.status_code == 200


def test_api_key_protects_non_health_routes(monkeypatch) -> None:
    monkeypatch.setenv("AAT_API_KEY", "test-secret")

    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/version").status_code == 401
    assert client.get("/version", headers={"X-AAT-API-Key": "test-secret"}).status_code == 200
