from __future__ import annotations

import logging
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kcal_tracker.database import SessionLocal
from kcal_tracker.models import QualityEvent, User
from kcal_tracker.services.admin_notifications import notify_admins
from kcal_tracker.services.users import UserService

logger = logging.getLogger(__name__)

ADMIN_NOTIFY_EVENTS = {
    "food_not_it",
    "food_ai_failed",
    "food_no_match",
    "food_search_cancelled",
}


async def record_quality_event(
    event_type: str,
    *,
    telegram_id: int | None = None,
    username: str | None = None,
    source: str | None = None,
    query: str | None = None,
    details: dict[str, Any] | None = None,
    notify_admin: bool = False,
) -> None:
    user: User | None = None
    try:
        async with SessionLocal() as session:
            if telegram_id is not None:
                user = await UserService(session).get_or_create(telegram_id, username)
            session.add(
                QualityEvent(
                    user_id=user.id if user else None,
                    event_type=event_type,
                    source=source,
                    query=_clip(query, 512),
                    details=details or {},
                )
            )
            await session.commit()
    except Exception:
        logger.warning("Failed to record quality event type=%s", event_type, exc_info=True)

    if notify_admin or event_type in ADMIN_NOTIFY_EVENTS:
        await _notify_quality_event(
            event_type,
            telegram_id=telegram_id,
            username=username,
            source=source,
            query=query,
            details=details or {},
        )


async def _notify_quality_event(
    event_type: str,
    *,
    telegram_id: int | None,
    username: str | None,
    source: str | None,
    query: str | None,
    details: dict[str, Any],
) -> None:
    label = f"@{username}" if username else str(telegram_id or "unknown")
    lines = [
        "⚠️ Quality event",
        "",
        f"type: {event_type}",
        f"user: {label}",
    ]
    if source:
        lines.append(f"source: {source}")
    if query:
        lines.extend(["", f"query: {query[:500]}"])
    if details:
        compact = ", ".join(f"{key}={value}" for key, value in list(details.items())[:5])
        lines.append(f"details: {compact}")
    await notify_admins("\n".join(lines), reply_markup=_quality_admin_keyboard())


def _quality_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📉 Quality", callback_data="admin:quality")],
            [InlineKeyboardButton(text="🚨 Alerts", callback_data="admin:alerts")],
        ]
    )


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value[:limit] if value else None
