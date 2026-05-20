from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select

from kcal_tracker.database import SessionLocal
from kcal_tracker.models import User
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.nutrition import (
    end_of_day_forecast,
    smart_evening_hint,
    smart_lunch_hint,
    smart_morning_hint,
)
from kcal_tracker.services.subscriptions import has_active_subscription

logger = logging.getLogger(__name__)


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            await _send_due_reminders(bot)
        except Exception:
            logger.exception("Reminder loop failed")
        await asyncio.sleep(60)


async def _send_due_reminders(bot: Bot) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.reminders_enabled.is_(True)))
        users = list(result.scalars())
        for user in users:
            now = datetime.now(ZoneInfo(user.timezone))
            today = now.date()
            if (
                user.weight_reminders_enabled
                and _is_due(
                    now,
                    user.weight_reminder_time or "09:00",
                    user.last_weight_reminder_date,
                )
            ):
                await bot.send_message(
                    user.telegram_id,
                    "Доброе утро. Если взвесился, нажми «⚖️ Вес».",
                )
                user.last_weight_reminder_date = today

            diary = DiaryService(session)
            if (
                user.meal_reminders_enabled
                and _is_due(
                    now,
                    user.breakfast_reminder_time or "10:00",
                    user.last_breakfast_reminder_date,
                )
            ):
                today_summary = await diary.today_summary(user)
                if _has_meal_entry(today_summary.entries, user.timezone, "breakfast"):
                    user.last_breakfast_reminder_date = today
                else:
                    yesterday = await diary.summary_for_day_offset(user, days_ago=1)
                    await bot.send_message(
                        user.telegram_id,
                        _breakfast_reminder_intro(today_summary)
                        + smart_morning_hint(yesterday),
                    )
                    user.last_breakfast_reminder_date = today

            if (
                user.meal_reminders_enabled
                and _is_due(
                    now,
                    user.lunch_reminder_time or "14:00",
                    user.last_lunch_reminder_date,
                )
            ):
                summary = await diary.today_summary(user)
                if _has_meal_entry(summary.entries, user.timezone, "lunch"):
                    user.last_lunch_reminder_date = today
                else:
                    patterns = (
                        await diary.nutrition_patterns(user)
                        if has_active_subscription(user)
                        else None
                    )
                    forecast = end_of_day_forecast(summary, patterns)
                    text = _lunch_reminder_intro(summary) + smart_lunch_hint(summary)
                    if forecast:
                        text += "\n" + forecast
                    await bot.send_message(
                        user.telegram_id,
                        text,
                    )
                    user.last_lunch_reminder_date = today

            if (
                user.meal_reminders_enabled
                and _is_due(
                    now,
                    user.dinner_reminder_time or "20:30",
                    user.last_dinner_reminder_date,
                )
            ):
                summary = await diary.today_summary(user)
                if _has_meal_entry(summary.entries, user.timezone, "dinner"):
                    user.last_dinner_reminder_date = today
                else:
                    await bot.send_message(
                        user.telegram_id,
                        _dinner_reminder_intro(summary) + smart_evening_hint(summary),
                    )
                    user.last_dinner_reminder_date = today

        await session.commit()


def _is_due(now: datetime, scheduled: str, last_sent_date) -> bool:
    if last_sent_date == now.date():
        return False
    hour, minute = _parse_time(scheduled)
    return now.hour * 60 + now.minute >= hour * 60 + minute


def _parse_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        return 9, 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return 9, 0
    return hour, minute


def _breakfast_reminder_intro(summary) -> str:
    if not summary.entries:
        return "Дневник пока пустой. Начнём мягко с завтрака.\n"
    return "Завтрак ещё не записан, но день уже начался.\n"


def _lunch_reminder_intro(summary) -> str:
    if not summary.entries:
        return "К обеду дневник пустой. Можно быстро занести всё, что уже было.\n"
    return "Обед ещё не записан. Сверимся, пока день не убежал.\n"


def _dinner_reminder_intro(summary) -> str:
    if not summary.entries:
        return "День почти прошёл без записей. Можно восстановить хотя бы крупными мазками.\n"
    if summary.kcal > summary.target_kcal:
        return "Ужин ещё не записан, а калории уже выше цели.\n"
    return "Ужин ещё не записан.\n"


def _has_meal_entry(entries, timezone_name: str, meal: str) -> bool:
    return any(_meal_key(entry.created_at, timezone_name) == meal for entry in entries)


def _meal_key(created_at: datetime, timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("Europe/Samara")
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    hour = created_at.astimezone(tz).hour
    if 5 <= hour < 12:
        return "breakfast"
    if 12 <= hour < 16:
        return "lunch"
    if 18 <= hour < 23:
        return "dinner"
    return "snacks"
