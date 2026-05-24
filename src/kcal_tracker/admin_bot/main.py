from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject
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


class AdminFlow(StatesGroup):
    waiting_user_lookup = State()
    waiting_grant_target = State()
    waiting_grant_days = State()


class AdminAccessMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: set[int]) -> None:
        self.admin_ids = admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, CallbackQuery):
            if event.from_user.id in self.admin_ids:
                return await handler(event, data)
            await event.answer("Доступ закрыт.", show_alert=True)
            logger.warning("Denied admin callback access for telegram_id=%s", event.from_user.id)
            return None
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
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.message.middleware(AdminAccessMiddleware(admin_ids))
    dispatcher.callback_query.middleware(AdminAccessMiddleware(admin_ids))
    dispatcher.include_router(router)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


@router.message(CommandStart())
@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(_main_menu_text(), reply_markup=_main_menu_keyboard())


@router.message(Command("id"))
async def id_command(message: Message) -> None:
    await message.answer(f"Твой Telegram ID: {message.from_user.id}", reply_markup=_main_menu_keyboard())


@router.callback_query(F.data == "admin:menu")
async def menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(_main_menu_text(), reply_markup=_main_menu_keyboard())
    await callback.answer()


@router.message(Command("today"))
async def today_command(message: Message) -> None:
    text = await _today_text()
    await message.answer(text, reply_markup=_today_keyboard())


@router.callback_query(F.data == "admin:today")
async def today_callback(callback: CallbackQuery) -> None:
    text = await _today_text()
    await callback.message.edit_text(text, reply_markup=_today_keyboard())
    await callback.answer("Обновлено")


async def _today_text() -> str:
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

    return "\n".join(
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


@router.message(Command("ai"))
async def ai_command(message: Message) -> None:
    text = await _ai_text()
    await message.answer(text, reply_markup=_ai_keyboard())


@router.callback_query(F.data == "admin:ai")
async def ai_callback(callback: CallbackQuery) -> None:
    text = await _ai_text()
    await callback.message.edit_text(text, reply_markup=_ai_keyboard())
    await callback.answer("Обновлено")


async def _ai_text() -> str:
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
    return "\n".join(lines)


@router.callback_query(F.data == "admin:user:ask")
async def ask_user_lookup(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.waiting_user_lookup)
    await callback.message.edit_text(
        "Введи Telegram ID или @username пользователя.",
        reply_markup=_cancel_keyboard(),
    )
    await callback.answer()


@router.message(Command("user"))
async def user_command(message: Message) -> None:
    target = _command_arg(message.text)
    if not target:
        await message.answer("Формат: /user <telegram_id|@username>")
        return

    async with SessionLocal() as session:
        user = await _find_user(session, target)
        if user is None:
            await message.answer("Пользователь не найден.", reply_markup=_main_menu_keyboard())
            return
        text = await _user_text(session, user)

    await message.answer(text, reply_markup=_user_keyboard(user.telegram_id))


@router.message(AdminFlow.waiting_user_lookup, F.text)
async def user_lookup_from_state(message: Message, state: FSMContext) -> None:
    target = (message.text or "").strip()
    async with SessionLocal() as session:
        user = await _find_user(session, target)
        if user is None:
            await message.answer("Пользователь не найден. Введи другой ID или нажми «Отмена».", reply_markup=_cancel_keyboard())
            return
        text = await _user_text(session, user)
    await state.clear()
    await message.answer(text, reply_markup=_user_keyboard(user.telegram_id))


@router.callback_query(F.data.startswith("admin:user:refresh:"))
async def refresh_user_callback(callback: CallbackQuery) -> None:
    target = callback.data.rsplit(":", 1)[1]
    async with SessionLocal() as session:
        user = await _find_user(session, target)
        if user is None:
            await callback.message.edit_text("Пользователь не найден.", reply_markup=_main_menu_keyboard())
            await callback.answer()
            return
        text = await _user_text(session, user)
    await callback.message.edit_text(text, reply_markup=_user_keyboard(user.telegram_id))
    await callback.answer("Обновлено")


@router.message(Command("grant"))
async def grant_command(message: Message) -> None:
    args = (message.text or "").split(maxsplit=2)
    if len(args) != 3:
        await message.answer("Формат: /grant <telegram_id|@username> <days>", reply_markup=_main_menu_keyboard())
        return
    target, days_text = args[1], args[2]
    try:
        days = int(days_text)
    except ValueError:
        await message.answer("Дни должны быть числом.", reply_markup=_main_menu_keyboard())
        return
    if days <= 0 or days > 365:
        await message.answer("Можно выдать от 1 до 365 дней.", reply_markup=_main_menu_keyboard())
        return

    text, user_id = await _grant_premium(target, days)
    await message.answer(text, reply_markup=_user_keyboard(user_id) if user_id else _main_menu_keyboard())


@router.callback_query(F.data == "admin:grant:ask")
async def ask_grant_target(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.waiting_grant_target)
    await callback.message.edit_text(
        "Кому выдать Premium? Введи Telegram ID или @username.",
        reply_markup=_cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:grant:target:"))
async def ask_grant_days_for_user(callback: CallbackQuery, state: FSMContext) -> None:
    target = callback.data.rsplit(":", 1)[1]
    await state.update_data(grant_target=target)
    await state.set_state(AdminFlow.waiting_grant_days)
    await callback.message.edit_text(
        f"На сколько дней выдать Premium пользователю {target}?",
        reply_markup=_grant_days_keyboard(int(target)),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_grant_target, F.text)
async def grant_target_from_state(message: Message, state: FSMContext) -> None:
    target = (message.text or "").strip()
    async with SessionLocal() as session:
        user = await _find_user(session, target)
    if user is None:
        await message.answer("Пользователь не найден. Введи другой ID или нажми «Отмена».", reply_markup=_cancel_keyboard())
        return
    await state.update_data(grant_target=str(user.telegram_id))
    await state.set_state(AdminFlow.waiting_grant_days)
    await message.answer(
        f"Пользователь найден: {user.telegram_id}.\nНа сколько дней выдать Premium?",
        reply_markup=_grant_days_keyboard(user.telegram_id),
    )


@router.callback_query(F.data.startswith("admin:grant:days:"))
async def grant_days_callback(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, _, target, days_text = callback.data.split(":", 4)
    days = int(days_text)
    text, user_id = await _grant_premium(target, days)
    await state.clear()
    await callback.message.edit_text(text, reply_markup=_user_keyboard(user_id) if user_id else _main_menu_keyboard())
    await callback.answer()


@router.message(AdminFlow.waiting_grant_days, F.text)
async def grant_days_from_state(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    target = data.get("grant_target")
    try:
        days = int((message.text or "").strip())
    except ValueError:
        await message.answer("Дни должны быть числом.", reply_markup=_cancel_keyboard())
        return
    text, user_id = await _grant_premium(str(target), days)
    if user_id:
        await state.clear()
    await message.answer(text, reply_markup=_user_keyboard(user_id) if user_id else _cancel_keyboard())


@router.callback_query(F.data == "admin:cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(_main_menu_text(), reply_markup=_main_menu_keyboard())
    await callback.answer("Отменено")


@router.message(F.text)
async def unknown_text(message: Message) -> None:
    await message.answer("Не понял команду. Выбери действие:", reply_markup=_main_menu_keyboard())


async def _user_text(session, user: User) -> str:
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
    return "\n".join(lines)


async def _grant_premium(target: str, days: int) -> tuple[str, int | None]:
    if days <= 0 or days > 365:
        return "Можно выдать от 1 до 365 дней.", None
    async with SessionLocal() as session:
        user = await _find_user(session, target)
        if user is None:
            return "Пользователь не найден.", None
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=days)
        await session.commit()
        await session.refresh(user)
        return (
            f"Premium выдан: {user.telegram_id} на {days} дн.\n"
            f"Активен до {user.subscription_expires_at:%d.%m.%Y %H:%M UTC}.",
            user.telegram_id,
        )


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


def _main_menu_text() -> str:
    return "\n".join(
        [
            "Kcal Admin",
            "",
            "Выбери раздел кнопками ниже.",
            "",
            "Команды тоже работают:",
            "/today, /ai, /user, /grant, /id",
        ]
    )


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Сегодня", callback_data="admin:today"),
                InlineKeyboardButton(text="🧠 AI", callback_data="admin:ai"),
            ],
            [
                InlineKeyboardButton(text="👤 Пользователь", callback_data="admin:user:ask"),
                InlineKeyboardButton(text="💎 Выдать Premium", callback_data="admin:grant:ask"),
            ],
        ]
    )


def _today_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:today"),
                InlineKeyboardButton(text="🧠 AI", callback_data="admin:ai"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _ai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:ai"),
                InlineKeyboardButton(text="📊 Сегодня", callback_data="admin:today"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _user_keyboard(telegram_id: int | None) -> InlineKeyboardMarkup:
    rows = []
    if telegram_id is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data=f"admin:user:refresh:{telegram_id}",
                ),
                InlineKeyboardButton(
                    text="💎 Premium",
                    callback_data=f"admin:grant:target:{telegram_id}",
                ),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(text="👤 Другой пользователь", callback_data="admin:user:ask"),
            InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _grant_days_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+1 день", callback_data=f"admin:grant:days:{telegram_id}:1"),
                InlineKeyboardButton(text="+7 дней", callback_data=f"admin:grant:days:{telegram_id}:7"),
            ],
            [
                InlineKeyboardButton(text="+30 дней", callback_data=f"admin:grant:days:{telegram_id}:30"),
                InlineKeyboardButton(text="+90 дней", callback_data=f"admin:grant:days:{telegram_id}:90"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")],
        ]
    )


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


if __name__ == "__main__":
    asyncio.run(main())
