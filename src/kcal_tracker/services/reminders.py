from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import or_, select

from kcal_tracker.bot.keyboards import subscription_cta_keyboard
from kcal_tracker.database import SessionLocal
from kcal_tracker.models import FoodEntry, User
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.nutrition import (
    end_of_day_forecast,
    smart_evening_hint,
    smart_lunch_hint,
    smart_morning_hint,
)
from kcal_tracker.services.subscriptions import has_active_subscription

logger = logging.getLogger(__name__)
INACTIVITY_REMINDER_DAYS = 3
INACTIVITY_REMINDER_REPEAT_DAYS = 7
INACTIVITY_REMINDER_TIME = "12:00"
SUBSCRIPTION_RENEWAL_REMINDER_DAYS = 2
SUBSCRIPTION_RENEWAL_REMINDER_TIME = "11:00"


async def reminder_loop(bot: Bot) -> None:
    while True:
        try:
            await _send_due_reminders(bot)
        except Exception:
            logger.exception("Reminder loop failed")
        await asyncio.sleep(60)


async def _send_due_reminders(bot: Bot) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(
                or_(
                    User.reminders_enabled.is_(True),
                    User.subscription_expires_at.is_not(None),
                )
            )
        )
        users = list(result.scalars())
        for user in users:
            now = datetime.now(ZoneInfo(user.timezone))
            today = now.date()
            if _subscription_renewal_reminder_due(now, user):
                await bot.send_message(
                    user.telegram_id,
                    _subscription_renewal_reminder_text(user, now),
                    reply_markup=subscription_cta_keyboard(),
                )
                user.last_subscription_reminder_date = today

            if not user.reminders_enabled:
                continue

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
                        reply_markup=evening_close_keyboard(),
                    )
                    user.last_dinner_reminder_date = today

            latest_entry_at = await _latest_food_entry_at(session, user)
            if _inactivity_reminder_due(
                now,
                latest_entry_at,
                user.created_at,
                user.last_inactivity_reminder_date,
            ):
                await bot.send_message(
                    user.telegram_id,
                    _inactivity_reminder_text(latest_entry_at, user.created_at, user.timezone),
                )
                user.last_inactivity_reminder_date = today

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


async def _latest_food_entry_at(session, user: User) -> datetime | None:
    result = await session.execute(
        select(FoodEntry.created_at)
        .where(FoodEntry.user_id == user.id)
        .order_by(FoodEntry.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _inactivity_reminder_due(
    now: datetime,
    latest_entry_at: datetime | None,
    user_created_at: datetime,
    last_sent_date,
) -> bool:
    if not _is_due(now, INACTIVITY_REMINDER_TIME, last_sent_date):
        return False
    if last_sent_date is not None:
        days_since_last_ping = (now.date() - last_sent_date).days
        if days_since_last_ping < INACTIVITY_REMINDER_REPEAT_DAYS:
            return False

    last_active_at = latest_entry_at or user_created_at
    last_active_date = _as_user_date(last_active_at, now.tzinfo or ZoneInfo("Europe/Samara"))
    return (now.date() - last_active_date).days >= INACTIVITY_REMINDER_DAYS


def _inactivity_reminder_text(
    latest_entry_at: datetime | None,
    user_created_at: datetime,
    timezone_name: str,
) -> str:
    tz = _safe_timezone(timezone_name)
    last_active_at = latest_entry_at or user_created_at
    days = max(0, (datetime.now(tz).date() - _as_user_date(last_active_at, tz)).days)
    prefix = f"Дневник молчит уже {days} дн." if days else "Дневник сегодня тихий."
    return (
        f"{prefix}\n"
        "Вернёмся мягко: просто запиши один приём пищи или напиши примерно, что было. "
        "Без идеальности, нам важнее снова поймать ритм."
    )


def _subscription_renewal_reminder_due(now: datetime, user: User) -> bool:
    if user.subscription_expires_at is None:
        return False
    if user.last_subscription_reminder_date is not None:
        days_since_last = (now.date() - user.last_subscription_reminder_date).days
        if days_since_last < 7:
            return False
    if not _is_due(now, SUBSCRIPTION_RENEWAL_REMINDER_TIME, user.last_subscription_reminder_date):
        return False
    expires_at = user.subscription_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    local_expires_at = expires_at.astimezone(now.tzinfo or ZoneInfo("Europe/Samara"))
    days_left = (local_expires_at.date() - now.date()).days
    return 0 <= days_left <= SUBSCRIPTION_RENEWAL_REMINDER_DAYS


def _subscription_renewal_reminder_text(user: User, now: datetime) -> str:
    expires_at = user.subscription_expires_at
    if expires_at is None:
        return "Premium скоро закончится. Можно продлить без перерыва в разделе «💎 Подписка»."
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    local_expires_at = expires_at.astimezone(now.tzinfo or ZoneInfo("Europe/Samara"))
    days_left = max(0, (local_expires_at.date() - now.date()).days)
    day_text = "сегодня" if days_left == 0 else f"через {days_left} {plural_day(days_left)}"
    return (
        f"Premium закончится {day_text}, {local_expires_at:%d.%m}.\n"
        "Можно продлить сейчас: новый срок добавится к текущему, без потери оставшихся дней."
    )


def plural_day(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "день"
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "дня"
    return "дней"


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
        return "День почти прошёл без записей. Закроем его без идеальности: хотя бы крупными мазками.\n"
    if summary.kcal > summary.target_kcal:
        return "Ужин ещё не записан, а калории уже выше цели. Можно просто сверить день и не добивать лишнее.\n"
    return "Ужин ещё не записан. Пора мягко закрыть день: еда, вода или быстрый взгляд на итог.\n"


def evening_close_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить ужин", callback_data="nav:add-food"),
                InlineKeyboardButton(text="💧 Вода", callback_data="water:add:250"),
            ],
            [InlineKeyboardButton(text="📊 Открыть сегодня", callback_data="nav:today")],
        ]
    )


def _has_meal_entry(entries, timezone_name: str, meal: str) -> bool:
    return any(_meal_key(entry.created_at, timezone_name) == meal for entry in entries)


def _meal_key(created_at: datetime, timezone_name: str) -> str:
    tz = _safe_timezone(timezone_name)
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


def _as_user_date(value: datetime, tz) -> object:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz).date()


def _safe_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo("Europe/Samara")
