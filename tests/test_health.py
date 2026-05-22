from __future__ import annotations

from fastapi.testclient import TestClient

from kcal_tracker.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
