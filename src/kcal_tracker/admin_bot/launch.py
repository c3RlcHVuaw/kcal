from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import httpx

from kcal_tracker.config import settings

PACKAGE_DIR = Path(__file__).resolve().parents[1]
LANDING_STATIC_DIR = PACKAGE_DIR / "landing_static"


async def launch_text() -> str:
    checks = await launch_checks()
    passed = sum(1 for item in checks if item[1])
    total = len(checks)
    lines = [
        "🚀 Launch checklist",
        "",
        f"Готово: {passed}/{total}",
        "",
    ]
    for label, ok, details in checks:
        icon = "✅" if ok else "⚠️"
        lines.append(f"{icon} {label}: {details}")
    if passed < total:
        lines.extend(
            [
                "",
                "Перед трафиком лучше закрыть жёлтые пункты.",
            ]
        )
    return "\n".join(lines)


async def launch_checks() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    ready_ok, ready_details = await launch_api_ready()
    checks.append(("API readiness", ready_ok, ready_details))
    checks.append(("Admin IDs", bool(settings.admin_ids), f"{len(settings.admin_ids)} configured"))
    checks.append(("OpenAI key", env_present("OPENAI_API_KEY"), secret_status("OPENAI_API_KEY")))
    yookassa_ok = bool(
        settings.yookassa_provider_token
        or (settings.yookassa_shop_id and settings.yookassa_secret_key)
    )
    checks.append(("YooKassa", yookassa_ok, "configured" if yookassa_ok else "not configured"))
    checks.append(
        (
            "Public API URL",
            settings.public_api_url.startswith(("http://", "https://"))
            and "127.0.0.1" not in settings.public_api_url
            and "localhost" not in settings.public_api_url,
            settings.public_api_url,
        )
    )
    checks.append(
        (
            "Broadcast all",
            not settings.admin_broadcast_all_enabled,
            "disabled" if not settings.admin_broadcast_all_enabled else "enabled",
        )
    )
    checks.append(
        (
            "AI safety cap",
            settings.ai_unlimited_safety_daily_request_limit > 0,
            (
                f"{settings.ai_unlimited_safety_daily_request_limit}/day"
                if settings.ai_unlimited_safety_daily_request_limit > 0
                else "off"
            ),
        )
    )
    checks.append(
        (
            "Alert loop",
            settings.admin_alert_interval_seconds > 0 and settings.admin_alert_cooldown_seconds > 0,
            f"{settings.admin_alert_interval_seconds}s / cooldown {settings.admin_alert_cooldown_seconds}s",
        )
    )
    backup_ok, backup_details = latest_backup_status()
    checks.append(("Fresh backup", backup_ok, backup_details))
    metrika_ok = landing_contains("109917758")
    checks.append(("Yandex Metrika", metrika_ok, "counter found" if metrika_ok else "counter missing"))
    return checks


async def launch_api_ready() -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get("http://api:3100/health/ready")
            payload = response.json()
        checks = payload.get("checks") or {}
        ok = response.status_code == 200 and payload.get("ok") is True
        details = ", ".join(f"{key}={value}" for key, value in checks.items()) or str(response.status_code)
        return ok, details
    except Exception as exc:
        return False, type(exc).__name__


def env_present(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def secret_status(name: str) -> str:
    return "set" if env_present(name) else "missing"


def latest_backup_status() -> tuple[bool, str]:
    backup_dir = Path("backups")
    backups = sorted(backup_dir.glob("*.sql.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not backups:
        return False, "no .sql.gz in /app/backups"
    latest = backups[0]
    age = datetime.now(UTC) - datetime.fromtimestamp(latest.stat().st_mtime, tz=UTC)
    hours = age.total_seconds() / 3600
    size_mb = latest.stat().st_size / 1024 / 1024
    return hours <= 25, f"{latest.name}, {hours:.1f}h ago, {size_mb:.1f} MB"


def landing_contains(text: str) -> bool:
    index_path = LANDING_STATIC_DIR / "index.html"
    try:
        return text in index_path.read_text(encoding="utf-8")
    except OSError:
        return False
