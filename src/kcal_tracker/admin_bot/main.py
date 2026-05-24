from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject
from sqlalchemy import func, select

from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.logging import configure_logging
from kcal_tracker.models import AIUsage, FoodEntry, Payment, User, WaterLog, WeightLog
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.subscriptions import has_active_subscription
from kcal_tracker.services.users import UserService

logger = logging.getLogger(__name__)
router = Router()


class AdminAccessMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: set[int]) -> None:
        self.admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)
        if event.from_user.id in self.admin_ids:
            return await handler(event, data)
        await event.answer(
            "Доступ закрыт.\n\n"
            f"Твой Telegram ID: {event.from_user.id}\n"
            "Добавь его в ADMIN_TELEGRAM_IDS на сервере, если это админ."
        )
        logger.warning("Denied admin bot access for telegram_id=%s", event.from_user.id)
        return None


async def main() -> None:
    configure_logging(settings.log_level)
    admin_ids = settings.admin_ids
    if not settings.admin_bot_token:
        raise RuntimeError("ADMIN_BOT_TOKEN is required for admin bot")
    if not admin_ids:
        logger.warning("ADMIN_TELEGRAM_IDS is empty; admin commands are locked for everyone")

    bot = Bot(settings.admin_bot_token)
    dispatcher = Dispatcher()
    dispatcher.message.middleware(AdminAccessMiddleware(admin_ids))
    dispatcher.include_router(router)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


@router.message(CommandStart())
@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "\n".join(
            [
                "Kcal Admin",
                "",
                "/today - дашборд за сегодня",
                "/ai - AI-запросы за сегодня",
                "/user <telegram_id|@username> - карточка пользователя",
                "/grant <telegram_id|@username> <days> - выдать Premium",
                "/id - показать твой Telegram ID",
            ]
        )
    )


@router.message(Command("id"))
async def id_command(message: Message) -> None:
    await message.answer(f"Твой Telegram ID: {message.from_user.id}")


@router.message(Command("today"))
async def today_command(message: Message) -> None:
    tz = ZoneInfo(settings.default_timezone)
    start, end = _today_bounds(tz)
    today = start.date()
    async with SessionLocal() as session:
        total_users = await _scalar(session, select(func.count(User.id)))
        new_users = await _scalar(
            session,
            select(func.count(User.id)).where(User.created_at >= start, User.created_at <= end),
        )
        active_food_users = await _scalar(
            session,
            select(func.count(func.distinct(FoodEntry.user_id))).where(
                FoodEntry.created_at >= start,
                FoodEntry.created_at <= end,
            ),
        )
        food_entries = await _scalar(
            session,
            select(func.count(FoodEntry.id)).where(
                FoodEntry.created_at >= start,
                FoodEntry.created_at <= end,
            ),
        )
        water_users = await _scalar(
            session,
            select(func.count(func.distinct(WaterLog.user_id))).where(
                WaterLog.created_at >= start,
                WaterLog.created_at <= end,
            ),
        )
        weight_users = await _scalar(
            session,
            select(func.count(func.distinct(WeightLog.user_id))).where(
                WeightLog.created_at >= start,
                WeightLog.created_at <= end,
            ),
        )
        ai_requests = await _scalar(
            session,
            select(func.coalesce(func.sum(AIUsage.request_count), 0)).where(
                AIUsage.usage_date == today
            ),
        )
        succeeded_payments = await _scalar(
            session,
            select(func.count(Payment.id)).where(
                Payment.status == "succeeded",
                Payment.created_at >= start,
                Payment.created_at <= end,
            ),
        )
        revenue_kopecks = await _scalar(
            session,
            select(func.coalesce(func.sum(Payment.amount_kopecks), 0)).where(
                Payment.status == "succeeded",
                Payment.created_at >= start,
                Payment.created_at <= end,
            ),
        )
        pending_payments = await _scalar(
            session,
            select(func.count(Payment.id)).where(
                Payment.status.in_(("pending", "waiting_for_capture")),
                Payment.expires_at >= datetime.now(UTC),
            ),
        )

    await message.answer(
        "\n".join(
            [
                "📊 Сегодня",
                "",
                f"Пользователи всего: {total_users}",
                f"Новые: {new_users}",
                f"С едой сегодня: {active_food_users}",
                f"Записей еды: {food_entries}",
                f"Воду записали: {water_users}",
                f"Вес записали: {weight_users}",
                "",
                f"AI-запросов: {ai_requests}",
                f"Успешных оплат: {succeeded_payments}",
                f"Выручка: {revenue_kopecks / 100:.0f} ₽",
                f"Ожидают оплаты: {pending_payments}",
            ]
        )
    )


@router.message(Command("ai"))
async def ai_command(message: Message) -> None:
    today = datetime.now(ZoneInfo(settings.default_timezone)).date()
    async with SessionLocal() as session:
        result = await session.execute(
            select(AIUsage.request_type, func.sum(AIUsage.request_count))
            .where(AIUsage.usage_date == today)
            .group_by(AIUsage.request_type)
            .order_by(func.sum(AIUsage.request_count).desc())
        )
        rows = [(request_type, int(count or 0)) for request_type, count in result.all()]
        top_users = await session.execute(
            select(User.telegram_id, User.username, func.sum(AIUsage.request_count).label("total"))
            .join(AIUsage, AIUsage.user_id == User.id)
            .where(AIUsage.usage_date == today)
            .group_by(User.id, User.telegram_id, User.username)
            .order_by(func.sum(AIUsage.request_count).desc())
            .limit(5)
        )

    lines = ["🧠 AI сегодня", ""]
    if rows:
        lines.extend(f"{request_type}: {count}" for request_type, count in rows)
    else:
        lines.append("Запросов пока нет.")
    lines.extend(["", "Топ пользователей:"])
    for telegram_id, username, total in top_users:
        label = f"@{username}" if username else str(telegram_id)
        lines.append(f"{label}: {int(total or 0)}")
    await message.answer("\n".join(lines))


@router.message(Command("user"))
async def user_command(message: Message) -> None:
    target = _command_arg(message.text)
    if not target:
        await message.answer("Формат: /user <telegram_id|@username>")
        return

    async with SessionLocal() as session:
        user = await _find_user(session, target)
        if user is None:
            await message.answer("Пользователь не найден.")
            return
        summary = await DiaryService(session).today_summary(user)
        recent_entries = await _recent_entries(session, user, limit=5)
        recent_payments = await _recent_payments(session, user, limit=3)
        ai_today = await _scalar(
            session,
            select(func.coalesce(func.sum(AIUsage.request_count), 0)).where(
                AIUsage.user_id == user.id,
                AIUsage.usage_date == datetime.now(ZoneInfo(user.timezone)).date(),
            ),
        )

    lines = [
        "👤 Пользователь",
        "",
        f"ID: {user.telegram_id}",
        f"Username: @{user.username}" if user.username else "Username: -",
        f"Onboarding: {'да' if user.onboarding_completed else 'нет'}",
        f"Premium: {'активен' if has_active_subscription(user) else 'нет'}",
        f"До: {user.subscription_expires_at:%d.%m.%Y %H:%M UTC}"
        if user.subscription_expires_at
        else "До: -",
        f"Цель: {user.daily_kcal_target} ккал",
        "",
        f"Сегодня: {summary.kcal:.0f}/{summary.target_kcal} ккал, записей {len(summary.entries)}",
        f"AI сегодня: {ai_today}",
        "",
        "Последняя еда:",
    ]
    if recent_entries:
        lines.extend(f"· {entry.food_name} - {entry.kcal:.0f} ккал" for entry in recent_entries)
    else:
        lines.append("нет записей")
    lines.extend(["", "Платежи:"])
    if recent_payments:
        lines.extend(
            f"· {payment.status} {payment.method} {payment.created_at:%d.%m %H:%M}"
            for payment in recent_payments
        )
    else:
        lines.append("нет платежей")
    await message.answer("\n".join(lines))


@router.message(Command("grant"))
async def grant_command(message: Message) -> None:
    args = (message.text or "").split(maxsplit=2)
    if len(args) != 3:
        await message.answer("Формат: /grant <telegram_id|@username> <days>")
        return
    target, days_text = args[1], args[2]
    try:
        days = int(days_text)
    except ValueError:
        await message.answer("Дни должны быть числом.")
        return
    if days <= 0 or days > 365:
        await message.answer("Можно выдать от 1 до 365 дней.")
        return

    async with SessionLocal() as session:
        user = await _find_user(session, target)
        if user is None:
            await message.answer("Пользователь не найден.")
            return
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=days)
        await session.commit()
        await session.refresh(user)

    await message.answer(
        f"Premium выдан: {user.telegram_id} на {days} дн.\n"
        f"Активен до {user.subscription_expires_at:%d.%m.%Y %H:%M UTC}."
    )


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    await message.answer("Не понял команду. Напиши /help.")


async def _find_user(session, target: str) -> User | None:
    user_service = UserService(session)
    value = target.strip()
    if value.startswith("@"):
        result = await session.execute(select(User).where(User.username == value[1:]))
        return result.scalar_one_or_none()
    try:
        telegram_id = int(value)
    except ValueError:
        result = await session.execute(select(User).where(User.username == value))
        return result.scalar_one_or_none()
    return await user_service.get_by_telegram_id(telegram_id)


async def _recent_entries(session, user: User, *, limit: int) -> list[FoodEntry]:
    result = await session.execute(
        select(FoodEntry)
        .where(FoodEntry.user_id == user.id)
        .order_by(FoodEntry.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def _recent_payments(session, user: User, *, limit: int) -> list[Payment]:
    result = await session.execute(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def _scalar(session, statement) -> int:
    result = await session.execute(statement)
    value = result.scalar_one()
    return int(value or 0)


def _today_bounds(tz: ZoneInfo) -> tuple[datetime, datetime]:
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def _command_arg(text: str | None) -> str | None:
    parts = (text or "").split(maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[1].strip()


if __name__ == "__main__":
    asyncio.run(main())
