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


def test_landing_page_is_served_with_seo_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Kcal Bot - бот для подсчета калорий в Telegram" in response.text
    assert '<link rel="canonical" href="https://kcal-bot.ru/" />' in response.text
    assert "https://t.me/trackerkcal_bot" in response.text
    assert "/landing/static/tracker.js?v=20260615-landing-stats" in response.text


def test_seo_discovery_files_are_served() -> None:
    with TestClient(app) as client:
        robots = client.get("/robots.txt")
        sitemap = client.get("/sitemap.xml")

    assert robots.status_code == 200
    assert "Sitemap: https://kcal-bot.ru/sitemap.xml" in robots.text
    assert "Disallow: /app" in robots.text
    assert sitemap.status_code == 200
    assert "<loc>https://kcal-bot.ru/</loc>" in sitemap.text
    assert "<loc>https://kcal-bot.ru/bot-dlya-podscheta-kaloriy</loc>" in sitemap.text
    assert "<loc>https://kcal-bot.ru/kalorii-po-foto</loc>" in sitemap.text
    assert "<loc>https://kcal-bot.ru/dnevnik-pitaniya-telegram</loc>" in sitemap.text


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
    assert "/webapp/me/food/parse-photo" in paths
    assert "/webapp/me/food/parse-photos" in paths
    assert "/webapp/me/food/scan-barcode" in paths
    assert "/webapp/me/food/barcode" in paths
    assert "/webapp/me/food/refine" in paths
    assert "/landing/events" in paths
    assert "/webapp/me/frequent" in paths
    assert "/webapp/me/weekly-missions/claim" in paths
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
