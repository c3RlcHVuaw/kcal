from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot
from sqlalchemy import func, select

from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.models import AIUsage, Payment, QualityEvent, User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminAlert:
    key: str
    text: str


async def admin_alert_loop(bot: Bot, admin_ids: set[int]) -> None:
    if not admin_ids:
        return

    last_sent_at: dict[str, float] = {}
    await asyncio.sleep(15)
    while True:
        try:
            alerts = await collect_admin_alerts()
            now = time.time()
            for alert in alerts:
                previous = last_sent_at.get(alert.key, 0)
                if now - previous < settings.admin_alert_cooldown_seconds:
                    continue
                await _notify_admins(bot, admin_ids, alert.text)
                last_sent_at[alert.key] = now
        except Exception:
            logger.exception("Failed to collect admin alerts")
        await asyncio.sleep(settings.admin_alert_interval_seconds)


async def collect_admin_alerts() -> list[AdminAlert]:
    alerts: list[AdminAlert] = []
    alerts.extend(_server_alerts())
    alerts.extend(await _api_alerts())
    alerts.extend(await _openai_alerts())
    alerts.extend(await _business_alerts())
    alerts.extend(await _quality_alerts())
    return alerts


def _server_alerts() -> list[AdminAlert]:
    alerts: list[AdminAlert] = []
    disk = shutil.disk_usage("/")
    disk_percent = disk.used / disk.total * 100 if disk.total else 0
    if disk_percent >= settings.admin_server_disk_percent_threshold:
        details = (
            f"Использовано {disk_percent:.1f}% "
            f"({_format_bytes(disk.used)} / {_format_bytes(disk.total)})."
        )
        alerts.append(
            AdminAlert(
                "server_disk_high",
                _alert_text("Диск почти заполнен", details),
            )
        )

    memory_percent = _memory_percent()
    if (
        memory_percent is not None
        and memory_percent >= settings.admin_server_memory_percent_threshold
    ):
        alerts.append(
            AdminAlert(
                "server_memory_high",
                _alert_text(
                    "Высокая загрузка памяти",
                    f"Использовано {memory_percent:.1f}% RAM.",
                ),
            )
        )

    load_per_cpu = _load_per_cpu()
    if (
        load_per_cpu is not None
        and settings.admin_server_load_per_cpu_threshold > 0
        and load_per_cpu >= settings.admin_server_load_per_cpu_threshold
    ):
        alerts.append(
            AdminAlert(
                "server_load_high",
                _alert_text(
                    "Сервер перегружен",
                    f"Load average на CPU: {load_per_cpu:.2f}. Порог: {settings.admin_server_load_per_cpu_threshold:.2f}.",
                ),
            )
        )
    return alerts


async def _api_alerts() -> list[AdminAlert]:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get("http://api:3100/health/ready")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return [
            AdminAlert(
                "api_ready_down",
                _alert_text("API недоступен", f"Ready-check не прошёл: {type(exc).__name__}."),
            )
        ]

    checks = payload.get("checks") or {}
    alerts: list[AdminAlert] = []
    if checks.get("database") is not True:
        alerts.append(
            AdminAlert(
                "database_unhealthy",
                _alert_text("Проблема с базой", "Readiness сообщает database=false."),
            )
        )
    if checks.get("redis") is not True:
        alerts.append(
            AdminAlert(
                "redis_unhealthy",
                _alert_text("Проблема с Redis", "Readiness сообщает redis=false."),
            )
        )
    return alerts


async def _openai_alerts() -> list[AdminAlert]:
    if settings.openai_monthly_budget_usd <= 0:
        return []
    if not settings.openai_admin_api_key:
        return [
            AdminAlert(
                "openai_admin_key_missing",
                _alert_text(
                    "OpenAI бюджет не мониторится",
                    "Задан месячный бюджет, но OPENAI_ADMIN_API_KEY не настроен.",
                ),
            )
        ]

    spent = await _openai_month_spent_usd()
    if spent is None:
        return [
            AdminAlert(
                "openai_costs_unavailable",
                _alert_text(
                    "OpenAI Costs API недоступен",
                    "Не удалось получить расходы организации. Проверь admin key и права.",
                ),
            )
        ]
    remaining = settings.openai_monthly_budget_usd - spent
    if remaining <= settings.openai_remaining_alert_usd:
        return [
            AdminAlert(
                "openai_budget_low",
                _alert_text(
                    "OpenAI бюджет почти закончился",
                    (
                        f"Осталось примерно ${remaining:.2f} из ${settings.openai_monthly_budget_usd:.2f}. "
                        f"Расход за месяц: ${spent:.2f}."
                    ),
                ),
            )
        ]
    return []


async def _business_alerts() -> list[AdminAlert]:
    now = datetime.now(UTC)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    async with SessionLocal() as session:
        pending = await _scalar(
            session,
            select(func.count(Payment.id)).where(
                Payment.status.in_(("pending", "waiting_for_capture")),
                Payment.expires_at >= now,
            ),
        )
        failed_hour = await _scalar(
            session,
            select(func.count(Payment.id)).where(
                Payment.status.in_(("canceled", "failed", "expired")),
                Payment.updated_at >= hour_ago,
            ),
        )
        no_onboarding = await _scalar(
            session,
            select(func.count(User.id)).where(
                User.created_at >= day_ago,
                User.onboarding_completed.is_(False),
            ),
        )
        ai_today = await _scalar(
            session,
            select(func.coalesce(func.sum(AIUsage.request_count), 0)).where(
                AIUsage.usage_date == now.date()
            ),
        )

    alerts: list[AdminAlert] = []
    if pending >= settings.admin_pending_payments_alert_threshold:
        alerts.append(
            AdminAlert(
                "payments_pending_high",
                _alert_text("Много ожидающих оплат", f"Сейчас pending-платежей: {pending}."),
            )
        )
    if failed_hour >= settings.admin_failed_payments_hour_threshold:
        alerts.append(
            AdminAlert(
                "payments_failed_high",
                _alert_text(
                    "Есть сбои оплат",
                    f"За последний час неуспешных платежей: {failed_hour}.",
                ),
            )
        )
    if no_onboarding >= settings.admin_no_onboarding_alert_threshold:
        alerts.append(
            AdminAlert(
                "onboarding_drop_high",
                _alert_text(
                    "Просадка onboarding",
                    f"За 24 часа не завершили onboarding: {no_onboarding}.",
                ),
            )
        )
    if ai_today == 0 and datetime.now(ZoneInfo(settings.default_timezone)).hour >= 12:
        alerts.append(
            AdminAlert(
                "ai_usage_zero_today",
                _alert_text("AI сегодня не используют", "В БД 0 AI-запросов за текущую дату."),
            )
        )
    return alerts


async def _quality_alerts() -> list[AdminAlert]:
    now = datetime.now(UTC)
    hour_ago = now - timedelta(hours=1)
    async with SessionLocal() as session:
        rows = await session.execute(
            select(QualityEvent.event_type, func.count(QualityEvent.id))
            .where(QualityEvent.created_at >= hour_ago)
            .group_by(QualityEvent.event_type)
        )
    counts = {event_type: int(count or 0) for event_type, count in rows}
    alerts: list[AdminAlert] = []
    if counts.get("food_not_it", 0) >= settings.admin_quality_not_it_hour_threshold:
        alerts.append(
            AdminAlert(
                "quality_not_it_spike",
                _alert_text(
                    "Всплеск «Не то»",
                    f"За последний час: {counts.get('food_not_it', 0)}. Проверь /quality.",
                ),
            )
        )
    if counts.get("food_ai_failed", 0) >= settings.admin_quality_ai_failed_hour_threshold:
        alerts.append(
            AdminAlert(
                "quality_ai_failed_spike",
                _alert_text(
                    "AI часто не разбирает еду",
                    f"За последний час AI failures: {counts.get('food_ai_failed', 0)}.",
                ),
            )
        )
    if counts.get("food_no_match", 0) >= settings.admin_quality_no_match_hour_threshold:
        alerts.append(
            AdminAlert(
                "quality_no_match_spike",
                _alert_text(
                    "Поиск часто ничего не находит",
                    f"За последний час no_match: {counts.get('food_no_match', 0)}.",
                ),
            )
        )
    return alerts


async def _openai_month_spent_usd() -> float | None:
    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.openai.com/v1/organization/costs",
                headers={"Authorization": f"Bearer {settings.openai_admin_api_key}"},
                params={
                    "start_time": int(month_start.timestamp()),
                    "end_time": int(now.timestamp()),
                    "bucket_width": "1d",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception:
        logger.warning("Failed to fetch OpenAI organization costs", exc_info=True)
        return None

    total = 0.0
    for bucket in payload.get("data", []):
        for item in bucket.get("results", []):
            amount = item.get("amount") or {}
            if str(amount.get("currency") or "usd").lower() == "usd":
                total += float(amount.get("value") or 0)
    return total


async def _notify_admins(bot: Bot, admin_ids: set[int], text: str) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            logger.warning("Failed to send admin alert to admin_id=%s", admin_id, exc_info=True)


async def _scalar(session, statement) -> int:
    result = await session.execute(statement)
    return int(result.scalar_one() or 0)


def _alert_text(title: str, details: str) -> str:
    return f"🚨 {title}\n\n{details}\n\nПроверь админку: /server или /alerts."


def _memory_percent() -> float | None:
    try:
        values: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as meminfo:
            for line in meminfo:
                name, raw_value = line.split(":", 1)
                values[name] = int(raw_value.strip().split()[0])
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", 0)
        if total <= 0:
            return None
        return (total - available) / total * 100
    except OSError:
        return None


def _load_per_cpu() -> float | None:
    try:
        load_1m = os.getloadavg()[0]
    except OSError:
        return None
    cpu_count = os.cpu_count() or 1
    return load_1m / cpu_count


def _format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
