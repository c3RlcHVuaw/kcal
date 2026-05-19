from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select

from kcal_tracker.database import SessionLocal
from kcal_tracker.models import User
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.nutrition import (
    smart_evening_hint,
    smart_lunch_hint,
    smart_morning_hint,
)

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
                yesterday = await diary.summary_for_day_offset(user, days_ago=1)
                await bot.send_message(
                    user.telegram_id,
                    "Доброе утро. Не забудь записать завтрак.\n"
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
                await bot.send_message(
                    user.telegram_id,
                    "Пора свериться с обедом.\n" + smart_lunch_hint(summary),
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
                await bot.send_message(
                    user.telegram_id,
                    "Не забудь внести ужин.\n" + smart_evening_hint(summary),
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
