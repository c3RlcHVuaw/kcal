from __future__ import annotations

from fastapi.testclient import TestClient

from kcal_tracker.api import routes
from kcal_tracker.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_webapp_shell_is_served() -> None:
    with TestClient(app) as client:
        response = client.get("/app")

    assert response.status_code == 200
    assert "Kcal Tracker" in response.text
    assert "tab-bar" in response.text


def test_openapi_exposes_external_client_routes() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/users/{telegram_id}/goals/weight" in paths
    assert "/users/{telegram_id}/analytics/week" in paths
    assert "/users/{telegram_id}/exports/food.csv" in paths
    assert "/webapp/me/today" in paths
    assert "/webapp/me/week" in paths
    assert "/webapp/me/body" in paths
    assert "/webapp/me/food/parse-text" in paths
    assert "/webapp/me/frequent" in paths
    assert "/webapp/me/activity" in paths
    assert "/webapp/me/exports/food.csv" in paths


def test_readiness_returns_ok_when_dependencies_are_available(monkeypatch) -> None:
    async def ok_database() -> bool:
        return True

    async def ok_redis() -> bool:
        return True

    monkeypatch.setattr(routes, "_check_database", ok_database)
    monkeypatch.setattr(routes, "_check_redis", ok_redis)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "checks": {"database": True, "redis": True}}


def test_readiness_returns_unavailable_when_dependency_fails(monkeypatch) -> None:
    async def ok_database() -> bool:
        return True

    async def failed_redis() -> bool:
        return False

    monkeypatch.setattr(routes, "_check_database", ok_database)
    monkeypatch.setattr(routes, "_check_redis", failed_redis)

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"ok": False, "checks": {"database": True, "redis": False}}
