from __future__ import annotations

import asyncio
import logging
import shutil
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from kcal_tracker.bot.keyboards import InlineKeyboardButton
from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.logging import configure_logging
from kcal_tracker.models import (
    AIUsage,
    FoodEntry,
    Payment,
    PromoCode,
    QualityEvent,
    User,
    WaterLog,
    WeightLog,
)
from kcal_tracker.services.admin_alerts import admin_alert_loop
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.subscriptions import (
    SubscriptionService,
    has_active_subscription,
    normalize_promo_code,
    promo_is_available,
)
from kcal_tracker.services.users import UserService

logger = logging.getLogger(__name__)
router = Router()


class AdminFlow(StatesGroup):
    waiting_user_lookup = State()
    waiting_grant_target = State()
    waiting_grant_days = State()
    waiting_promo_create = State()
    waiting_broadcast_text = State()
    waiting_support_reply = State()


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
    admin_alerts = asyncio.create_task(admin_alert_loop(bot, admin_ids))
    daily_digest = asyncio.create_task(admin_daily_digest_loop(bot, admin_ids))
    try:
        await dispatcher.start_polling(bot)
    finally:
        admin_alerts.cancel()
        daily_digest.cancel()
        with suppress(asyncio.CancelledError):
            await admin_alerts
        with suppress(asyncio.CancelledError):
            await daily_digest
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


@router.callback_query(F.data == "admin:ops")
async def ops_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Операции и мониторинг:", reply_markup=_ops_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:crm")
async def crm_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Пользователи, подписки и поддержка:", reply_markup=_crm_keyboard())
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


@router.message(Command("digest"))
async def digest_command(message: Message) -> None:
    text = await _digest_text()
    await message.answer(text, reply_markup=_today_keyboard())


async def admin_daily_digest_loop(bot: Bot, admin_ids: set[int]) -> None:
    if not admin_ids:
        return
    sent_dates: set[str] = set()
    await asyncio.sleep(20)
    while True:
        try:
            now = datetime.now(ZoneInfo(settings.default_timezone))
            scheduled_hour, scheduled_minute = _parse_hhmm(settings.admin_daily_digest_time, "09:05")
            key = now.date().isoformat()
            is_due = now.hour * 60 + now.minute >= scheduled_hour * 60 + scheduled_minute
            if is_due and key not in sent_dates:
                text = await _digest_text()
                for admin_id in admin_ids:
                    await bot.send_message(admin_id, text, reply_markup=_today_keyboard())
                sent_dates.add(key)
                sent_dates = {key}
        except Exception:
            logger.exception("Failed to send daily admin digest")
        await asyncio.sleep(60)


async def _digest_text() -> str:
    today = await _today_text()
    quality = await _quality_text()
    alerts = await _alerts_text()
    return "\n\n".join(["🗞 Ежедневный дайджест", today, quality, alerts])


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


@router.message(Command("server"))
async def server_command(message: Message) -> None:
    text = await _server_text()
    await message.answer(text, reply_markup=_server_keyboard())


@router.callback_query(F.data == "admin:server")
async def server_callback(callback: CallbackQuery) -> None:
    text = await _server_text()
    await callback.message.edit_text(text, reply_markup=_server_keyboard())
    await callback.answer("Обновлено")


@router.message(Command("openai"))
@router.message(Command("balance"))
async def openai_command(message: Message) -> None:
    text = await _openai_text()
    await message.answer(text, reply_markup=_openai_keyboard())


@router.callback_query(F.data == "admin:openai")
async def openai_callback(callback: CallbackQuery) -> None:
    text = await _openai_text()
    await callback.message.edit_text(text, reply_markup=_openai_keyboard())
    await callback.answer("Обновлено")


@router.message(Command("alerts"))
async def alerts_command(message: Message) -> None:
    text = await _alerts_text()
    await message.answer(text, reply_markup=_alerts_keyboard())


@router.callback_query(F.data == "admin:alerts")
async def alerts_callback(callback: CallbackQuery) -> None:
    text = await _alerts_text()
    await callback.message.edit_text(text, reply_markup=_alerts_keyboard())
    await callback.answer("Обновлено")


@router.message(Command("quality"))
async def quality_command(message: Message) -> None:
    text = await _quality_text()
    await message.answer(text, reply_markup=_quality_keyboard())


@router.callback_query(F.data == "admin:quality")
async def quality_callback(callback: CallbackQuery) -> None:
    text = await _quality_text()
    await callback.message.edit_text(text, reply_markup=_quality_keyboard())
    await callback.answer("Обновлено")


@router.callback_query(F.data.startswith("admin:quality:"))
async def quality_filtered_callback(callback: CallbackQuery) -> None:
    mode = callback.data.rsplit(":", 1)[1]
    text = await _quality_text(mode=mode)
    await callback.message.edit_text(text, reply_markup=_quality_keyboard(mode=mode))
    await callback.answer("Обновлено")


@router.message(Command("funnel"))
async def funnel_command(message: Message) -> None:
    text = await _funnel_text()
    await message.answer(text, reply_markup=_funnel_keyboard())


@router.callback_query(F.data == "admin:funnel")
async def funnel_callback(callback: CallbackQuery) -> None:
    text = await _funnel_text()
    await callback.message.edit_text(text, reply_markup=_funnel_keyboard())
    await callback.answer("Обновлено")


@router.message(Command("payments"))
async def payments_command(message: Message) -> None:
    text = await _payments_text()
    await message.answer(text, reply_markup=_payments_keyboard())


@router.callback_query(F.data == "admin:payments")
async def payments_callback(callback: CallbackQuery) -> None:
    text = await _payments_text()
    await callback.message.edit_text(text, reply_markup=_payments_keyboard())
    await callback.answer("Обновлено")


@router.message(Command("promos"))
async def promos_command(message: Message) -> None:
    text = await _promos_text()
    await message.answer(text, reply_markup=_promos_keyboard())


@router.callback_query(F.data == "admin:promos")
async def promos_callback(callback: CallbackQuery) -> None:
    text = await _promos_text()
    await callback.message.edit_text(text, reply_markup=_promos_keyboard())
    await callback.answer("Обновлено")


@router.callback_query(F.data == "admin:promos:create")
async def ask_promo_create(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.waiting_promo_create)
    await callback.message.edit_text(
        "\n".join(
            [
                "Создание промокода",
                "",
                "Формат:",
                "CODE 20 100 2026-06-30 описание",
                "",
                "Где 20 — скидка %, 100 — лимит использований.",
                "Лимит, дата и описание необязательны.",
            ]
        ),
        reply_markup=_cancel_keyboard(),
    )
    await callback.answer()


@router.message(Command("promo"))
async def promo_create_command(message: Message) -> None:
    raw = _command_arg(message.text)
    if not raw:
        await message.answer(
            "Формат: /promo CODE 20 [max_uses] [YYYY-MM-DD] [описание]",
            reply_markup=_promos_keyboard(),
        )
        return
    text = await _create_promo_from_text(raw)
    await message.answer(text, reply_markup=_promos_keyboard())


@router.message(Command("promo_off"))
async def promo_disable_command(message: Message) -> None:
    target = _command_arg(message.text)
    if not target:
        await message.answer("Формат: /promo_off <id|CODE>", reply_markup=_promos_keyboard())
        return
    text = await _disable_promo_by_target(target)
    await message.answer(text, reply_markup=_promos_keyboard())


@router.message(AdminFlow.waiting_promo_create, F.text)
async def promo_create_from_state(message: Message, state: FSMContext) -> None:
    text = await _create_promo_from_text(message.text or "")
    if text.startswith("Не понял"):
        await message.answer(text, reply_markup=_cancel_keyboard())
        return
    await state.clear()
    await message.answer(text, reply_markup=_promos_keyboard())


@router.callback_query(F.data.startswith("admin:promo:disable:"))
async def promo_disable_callback(callback: CallbackQuery) -> None:
    promo_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        promo = await SubscriptionService(session).disable_promo(promo_id)
    if promo is None:
        await callback.answer("Промокод не найден.", show_alert=True)
        return
    text = await _promos_text()
    await callback.message.edit_text(text, reply_markup=_promos_keyboard())
    await callback.answer(f"{promo.code} отключён")


@router.message(Command("growth"))
async def growth_command(message: Message) -> None:
    text = await _growth_text()
    await message.answer(text, reply_markup=_growth_keyboard())


@router.callback_query(F.data == "admin:growth")
async def growth_callback(callback: CallbackQuery) -> None:
    text = await _growth_text()
    await callback.message.edit_text(text, reply_markup=_growth_keyboard())
    await callback.answer("Обновлено")


@router.message(Command("config"))
async def config_command(message: Message) -> None:
    await message.answer(_config_text(), reply_markup=_config_keyboard())


@router.callback_query(F.data == "admin:config")
async def config_callback(callback: CallbackQuery) -> None:
    await callback.message.edit_text(_config_text(), reply_markup=_config_keyboard())
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


@router.message(Command("broadcast"))
async def broadcast_command(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminFlow.waiting_broadcast_text)
    await state.update_data(broadcast_segment="active_7")
    await message.answer(
        "Рассылка активным за 7 дней. Отправь текст сообщения.",
        reply_markup=_broadcast_segment_keyboard("active_7"),
    )


@router.callback_query(F.data == "admin:broadcast")
async def broadcast_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.waiting_broadcast_text)
    await state.update_data(broadcast_segment="active_7")
    await callback.message.edit_text(
        "Выбери сегмент и отправь текст рассылки.",
        reply_markup=_broadcast_segment_keyboard("active_7"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:broadcast:segment:"))
async def broadcast_segment_callback(callback: CallbackQuery, state: FSMContext) -> None:
    segment = callback.data.rsplit(":", 1)[1]
    await state.set_state(AdminFlow.waiting_broadcast_text)
    await state.update_data(broadcast_segment=segment)
    await callback.message.edit_text(
        f"Сегмент: {_broadcast_segment_title(segment)}.\nОтправь текст рассылки.",
        reply_markup=_broadcast_segment_keyboard(segment),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_broadcast_text, F.text)
async def broadcast_text_from_state(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст пустой. Отправь сообщение для рассылки.", reply_markup=_cancel_keyboard())
        return
    data = await state.get_data()
    segment = str(data.get("broadcast_segment") or "active_7")
    async with SessionLocal() as session:
        recipients = await _broadcast_recipients(session, segment)
    await state.update_data(broadcast_text=text)
    await message.answer(
        "\n".join(
            [
                "Предпросмотр рассылки",
                "",
                f"Сегмент: {_broadcast_segment_title(segment)}",
                f"Получателей: {len(recipients)}",
                "",
                text,
            ]
        ),
        reply_markup=_broadcast_confirm_keyboard(),
    )


@router.callback_query(F.data == "admin:broadcast:send")
async def broadcast_send_callback(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    segment = str(data.get("broadcast_segment") or "active_7")
    text = str(data.get("broadcast_text") or "").strip()
    if not text:
        await callback.answer("Нет текста рассылки.", show_alert=True)
        return
    async with SessionLocal() as session:
        recipients = await _broadcast_recipients(session, segment)
    sent = await _send_broadcast(recipients, text)
    await state.clear()
    await callback.message.edit_text(
        f"Рассылка завершена: {sent}/{len(recipients)} отправлено.",
        reply_markup=_main_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:support:reply:"))
async def support_reply_callback(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.data.rsplit(":", 1)[1]
    await state.set_state(AdminFlow.waiting_support_reply)
    await state.update_data(support_user_id=user_id)
    await callback.message.edit_text(
        f"Ответ пользователю {user_id}. Отправь текст одним сообщением.",
        reply_markup=_cancel_keyboard(),
    )
    await callback.answer()


@router.message(AdminFlow.waiting_support_reply, F.text)
async def support_reply_from_state(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    user_id = int(data["support_user_id"])
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст пустой. Напиши ответ или нажми «Отмена».", reply_markup=_cancel_keyboard())
        return
    sent = await _send_user_message(user_id, f"Ответ поддержки:\n\n{text}")
    await state.clear()
    await message.answer(
        "Ответ отправлен." if sent else "Не удалось отправить ответ пользователю.",
        reply_markup=_main_menu_keyboard(),
    )


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


async def _server_text() -> str:
    uptime = _format_seconds(time.time() - _process_started_at())
    disk = shutil.disk_usage("/")
    mem = _memory_info()
    api_status = await _api_ready_status()
    return "\n".join(
        [
            "🖥 Сервер",
            "",
            f"API: {api_status}",
            f"APP_ENV: {settings.app_env}",
            f"Процесс admin-bot: {uptime}",
            f"Диск: {_format_bytes(disk.used)} / {_format_bytes(disk.total)}",
            f"Память: {mem}",
            "",
            "Контейнеры смотри через docker compose ps на сервере.",
        ]
    )


async def _openai_text() -> str:
    api_key = settings.openai_admin_api_key or settings.openai_api_key
    local_ai = await _local_ai_cost_hint()
    if not api_key:
        return "💳 OpenAI\n\nOPENAI_API_KEY не настроен.\n\n" + local_ai

    now = datetime.now(UTC)
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.openai.com/v1/organization/costs",
                headers={"Authorization": f"Bearer {api_key}"},
                params={
                    "start_time": int(month_start.timestamp()),
                    "end_time": int(now.timestamp()),
                    "bucket_width": "1d",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        return "\n".join(
            [
                "💳 OpenAI",
                "",
                "Не удалось получить Costs API.",
                f"Причина: {type(exc).__name__}",
                "Нужен ключ с правами на organization costs.",
                "",
                local_ai,
            ]
        )

    total_by_currency: dict[str, float] = {}
    for bucket in payload.get("data", []):
        for item in bucket.get("results", []):
            amount = item.get("amount") or {}
            currency = str(amount.get("currency") or "usd").upper()
            total_by_currency[currency] = total_by_currency.get(currency, 0.0) + float(
                amount.get("value") or 0
            )
    totals = ", ".join(f"{value:.2f} {currency}" for currency, value in total_by_currency.items())
    lines = ["💳 OpenAI", "", f"Costs API за месяц: {totals or '0'}"]
    if settings.openai_monthly_budget_usd > 0:
        spent_usd = total_by_currency.get("USD", 0.0)
        remaining = settings.openai_monthly_budget_usd - spent_usd
        lines.append(
            f"Бюджет: ${settings.openai_monthly_budget_usd:.2f}, осталось примерно ${remaining:.2f}"
        )
        lines.append(f"Порог алерта: ${settings.openai_remaining_alert_usd:.2f}")
    else:
        lines.append("Месячный бюджет не задан: OPENAI_MONTHLY_BUDGET_USD=0")
    lines.extend(["", local_ai])
    return "\n".join(lines)


async def _local_ai_cost_hint() -> str:
    today = datetime.now(ZoneInfo(settings.default_timezone)).date()
    month_start = today.replace(day=1)
    async with SessionLocal() as session:
        today_count = await _scalar(
            session,
            select(func.coalesce(func.sum(AIUsage.request_count), 0)).where(
                AIUsage.usage_date == today
            ),
        )
        month_count = await _scalar(
            session,
            select(func.coalesce(func.sum(AIUsage.request_count), 0)).where(
                AIUsage.usage_date >= month_start
            ),
        )
    return f"Локально в БД: сегодня {today_count} AI-запросов, месяц {month_count}."


async def _alerts_text() -> str:
    tz = ZoneInfo(settings.default_timezone)
    start, end = _today_bounds(tz)
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        pending = await _scalar(
            session,
            select(func.count(Payment.id)).where(
                Payment.status.in_(("pending", "waiting_for_capture")),
                Payment.expires_at >= now,
            ),
        )
        expired = await _scalar(
            session,
            select(func.count(Payment.id)).where(
                Payment.status.in_(("pending", "waiting_for_capture")),
                Payment.expires_at < now,
            ),
        )
        not_onboarded = await _scalar(
            session,
            select(func.count(User.id)).where(
                User.created_at >= start,
                User.created_at <= end,
                User.onboarding_completed.is_(False),
            ),
        )
        high_ai = await session.execute(
            select(User.telegram_id, User.username, func.sum(AIUsage.request_count).label("total"))
            .join(AIUsage, AIUsage.user_id == User.id)
            .where(AIUsage.usage_date == start.date())
            .group_by(User.id, User.telegram_id, User.username)
            .having(func.sum(AIUsage.request_count) >= 20)
            .order_by(func.sum(AIUsage.request_count).desc())
            .limit(5)
        )
    lines = ["🚨 Alerts", "", f"Ожидают оплаты: {pending}", f"Просроченные pending: {expired}", f"Новые без onboarding: {not_onboarded}", ""]
    lines.append("Высокий AI сегодня:")
    rows = list(high_ai)
    if rows:
        for telegram_id, username, total in rows:
            label = f"@{username}" if username else str(telegram_id)
            lines.append(f"· {label}: {int(total or 0)}")
    else:
        lines.append("нет")
    return "\n".join(lines)


async def _quality_text(mode: str = "overview") -> str:
    tz = ZoneInfo(settings.default_timezone)
    start, end = _today_bounds(tz)
    event_filter = _quality_event_filter(mode)
    async with SessionLocal() as session:
        totals = await session.execute(
            select(QualityEvent.event_type, func.count(QualityEvent.id))
            .where(QualityEvent.created_at >= start, QualityEvent.created_at <= end)
            .group_by(QualityEvent.event_type)
            .order_by(func.count(QualityEvent.id).desc())
        )
        top_queries = await session.execute(
            select(QualityEvent.query, func.count(QualityEvent.id))
            .where(
                QualityEvent.created_at >= start,
                QualityEvent.created_at <= end,
                QualityEvent.query.is_not(None),
                *event_filter,
            )
            .group_by(QualityEvent.query)
            .order_by(func.count(QualityEvent.id).desc())
            .limit(5)
        )
        top_users = await session.execute(
            select(User.telegram_id, User.username, func.count(QualityEvent.id))
            .join(User, User.id == QualityEvent.user_id)
            .where(
                QualityEvent.created_at >= start,
                QualityEvent.created_at <= end,
                *event_filter,
            )
            .group_by(User.id, User.telegram_id, User.username)
            .order_by(func.count(QualityEvent.id).desc())
            .limit(5)
        )
        recent = await session.execute(
            select(QualityEvent)
            .where(*event_filter)
            .order_by(QualityEvent.created_at.desc())
            .limit(10)
        )

    lines = [f"📉 Quality · {_quality_mode_title(mode)}", "", "Сегодня:"]
    total_rows = list(totals)
    if total_rows:
        for event_type, count in total_rows:
            lines.append(f"{event_type}: {count}")
    else:
        lines.append("событий нет")

    lines.extend(["", "Топ запросов:"])
    query_rows = [(query, count) for query, count in top_queries if query]
    if query_rows:
        for query, count in query_rows:
            label = query.replace("\n", " ")
            if len(label) > 46:
                label = label[:43] + "..."
            lines.append(f"· {label}: {count}")
    else:
        lines.append("нет")

    lines.extend(["", "Пользователи с ошибками:"])
    user_rows = list(top_users)
    if user_rows:
        for telegram_id, username, count in user_rows:
            label = f"@{username}" if username else str(telegram_id)
            lines.append(f"· {label}: {count}")
    else:
        lines.append("нет")

    lines.extend(["", "Последние:"])
    events = list(recent.scalars())
    if not events:
        lines.append("нет")
        return "\n".join(lines)

    for event in events:
        query = (event.query or "").replace("\n", " ")
        if len(query) > 54:
            query = query[:51] + "..."
        source = f" / {event.source}" if event.source else ""
        lines.append(f"· {event.event_type}{source}: {query or 'без текста'}")
    return "\n".join(lines)


def _quality_event_filter(mode: str) -> list:
    if mode == "not-it":
        return [QualityEvent.event_type == "food_not_it"]
    if mode == "ai":
        return [QualityEvent.event_type == "food_ai_failed"]
    if mode == "search":
        return [QualityEvent.event_type.in_(["food_no_match", "food_search_cancelled"])]
    return []


def _quality_mode_title(mode: str) -> str:
    return {
        "not-it": "Не то",
        "ai": "AI ошибки",
        "search": "Поиск",
    }.get(mode, "обзор")


async def _funnel_text() -> str:
    tz = ZoneInfo(settings.default_timezone)
    today_start, today_end = _today_bounds(tz)
    week_start = today_start - timedelta(days=6)
    month_start = today_start - timedelta(days=29)
    async with SessionLocal() as session:
        today = await _funnel_metrics(session, today_start, today_end)
        week = await _funnel_metrics(session, week_start, today_end)
        month = await _funnel_metrics(session, month_start, today_end)
    return "\n".join(
        [
            "🧭 Продуктовая воронка",
            "",
            _funnel_period_text("Сегодня", today),
            "",
            _funnel_period_text("7 дней", week),
            "",
            _funnel_period_text("30 дней", month),
        ]
    )


async def _funnel_metrics(session, start: datetime, end: datetime) -> dict[str, int]:
    cohort_filter = (User.created_at >= start, User.created_at <= end)
    started = await _scalar(session, select(func.count(User.id)).where(*cohort_filter))
    onboarded = await _scalar(
        session,
        select(func.count(User.id)).where(*cohort_filter, User.onboarding_completed.is_(True)),
    )
    first_food = await _scalar(
        session,
        select(func.count(func.distinct(FoodEntry.user_id)))
        .join(User, User.id == FoodEntry.user_id)
        .where(*cohort_filter),
    )
    active_3_days = await _scalar(
        session,
        select(func.count())
        .select_from(
            select(FoodEntry.user_id)
            .join(User, User.id == FoodEntry.user_id)
            .where(*cohort_filter)
            .group_by(FoodEntry.user_id)
            .having(func.count(func.distinct(func.date(FoodEntry.created_at))) >= 3)
            .subquery()
        ),
    )
    ai_users = await _scalar(
        session,
        select(func.count(func.distinct(AIUsage.user_id)))
        .join(User, User.id == AIUsage.user_id)
        .where(*cohort_filter),
    )
    payers = await _scalar(
        session,
        select(func.count(func.distinct(Payment.user_id)))
        .join(User, User.id == Payment.user_id)
        .where(*cohort_filter, Payment.status == "succeeded"),
    )
    return {
        "started": started,
        "onboarded": onboarded,
        "first_food": first_food,
        "active_3_days": active_3_days,
        "ai_users": ai_users,
        "payers": payers,
    }


def _funnel_period_text(title: str, metrics: dict[str, int]) -> str:
    started = metrics["started"]
    return "\n".join(
        [
            title,
            f"/start: {started}",
            f"Onboarding: {metrics['onboarded']} ({_percent(metrics['onboarded'], started)})",
            f"Первая еда: {metrics['first_food']} ({_percent(metrics['first_food'], started)})",
            f"3 активных дня: {metrics['active_3_days']} ({_percent(metrics['active_3_days'], started)})",
            f"AI: {metrics['ai_users']} ({_percent(metrics['ai_users'], started)})",
            f"Оплата: {metrics['payers']} ({_percent(metrics['payers'], started)})",
        ]
    )


def _percent(value: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{value / total:.0%}"


async def _payments_text() -> str:
    async with SessionLocal() as session:
        recent = await session.execute(select(Payment).order_by(Payment.created_at.desc()).limit(8))
        by_status = await session.execute(
            select(Payment.status, func.count(Payment.id)).group_by(Payment.status).order_by(func.count(Payment.id).desc())
        )
    lines = ["💰 Платежи", "", "По статусам:"]
    for status, count in by_status:
        lines.append(f"{status}: {count}")
    lines.extend(["", "Последние:"])
    payments = list(recent.scalars())
    if payments:
        for payment in payments:
            amount = f"{(payment.amount_kopecks or 0) / 100:.0f} ₽" if payment.amount_kopecks else f"{payment.amount_stars or 0} ⭐"
            lines.append(f"· {payment.status} {payment.method} {amount} user={payment.user_id}")
    else:
        lines.append("нет платежей")
    return "\n".join(lines)


async def _promos_text() -> str:
    async with SessionLocal() as session:
        promos = await SubscriptionService(session).active_promos(limit=15)
        promo_payments = await _scalar(
            session,
            select(func.count(Payment.id)).where(Payment.promo_code_id.is_not(None)),
        )
    lines = [
        "🎟 Промокоды",
        "",
        f"Оплат с промокодом: {promo_payments}",
        "Создать: /promo CODE 20 [max] [YYYY-MM-DD] [note]",
        "Отключить: /promo_off <id|CODE>",
        "",
        "Последние:",
    ]
    if not promos:
        lines.append("нет промокодов")
        return "\n".join(lines)
    now = datetime.now(UTC)
    for promo in promos:
        status = "активен" if promo_is_available(promo, now=now) else "выкл/истёк"
        limit = "∞" if promo.max_uses is None else str(promo.max_uses)
        expires = promo.expires_at.strftime("%d.%m.%Y") if promo.expires_at else "без срока"
        lines.append(
            f"· #{promo.id} {promo.code}: -{promo.discount_percent}% "
            f"{promo.used_count}/{limit}, {expires}, {status}"
        )
        if promo.note:
            lines.append(f"  {promo.note}")
    return "\n".join(lines)


async def _create_promo_from_text(raw: str) -> str:
    parsed = _parse_promo_create_text(raw)
    if parsed is None:
        return "Не понял формат. Пример: NEWYEAR 20 100 2026-06-30 январская акция"
    code, discount_percent, max_uses, expires_at, note = parsed
    async with SessionLocal() as session:
        try:
            promo = await SubscriptionService(session).create_promo(
                code=code,
                discount_percent=discount_percent,
                max_uses=max_uses,
                expires_at=expires_at,
                note=note,
            )
        except IntegrityError:
            await session.rollback()
            return "Промокод с таким кодом уже существует."
        except ValueError as exc:
            return str(exc)
    limit = "без лимита" if promo.max_uses is None else f"лимит {promo.max_uses}"
    expires = "без срока" if promo.expires_at is None else promo.expires_at.strftime("%d.%m.%Y")
    return f"Промокод создан: {promo.code}, скидка {promo.discount_percent}%, {limit}, {expires}."


async def _disable_promo_by_target(target: str) -> str:
    value = target.strip()
    async with SessionLocal() as session:
        if value.isdigit():
            promo = await SubscriptionService(session).disable_promo(int(value))
        else:
            code = normalize_promo_code(value)
            result = await session.execute(select(PromoCode).where(PromoCode.code == code))
            found = result.scalar_one_or_none()
            promo = await SubscriptionService(session).disable_promo(found.id) if found else None
    if promo is None:
        return "Промокод не найден."
    return f"Промокод {promo.code} отключён."


def _parse_promo_create_text(
    raw: str,
) -> tuple[str, int, int | None, datetime | None, str | None] | None:
    parts = raw.split()
    if len(parts) < 2:
        return None
    code = normalize_promo_code(parts[0])
    try:
        discount_percent = int(parts[1])
    except ValueError:
        return None
    index = 2
    max_uses: int | None = None
    expires_at: datetime | None = None
    if len(parts) > index:
        try:
            max_uses = int(parts[index])
            if max_uses <= 0:
                return None
            index += 1
        except ValueError:
            pass
    if len(parts) > index:
        try:
            expires_date = datetime.strptime(parts[index], "%Y-%m-%d").date()
            expires_at = datetime.combine(expires_date, datetime.max.time(), tzinfo=UTC)
            index += 1
        except ValueError:
            pass
    note = " ".join(parts[index:]).strip() or None
    return code, discount_percent, max_uses, expires_at, note


async def _growth_text() -> str:
    async with SessionLocal() as session:
        invited = await _scalar(session, select(func.count(User.id)).where(User.referred_by_user_id.is_not(None)))
        rewarded = await _scalar(session, select(func.count(User.id)).where(User.active_referral_rewarded_at.is_not(None)))
        paid_rewarded = await _scalar(session, select(func.count(User.id)).where(User.referral_rewarded_at.is_not(None)))
    return "\n".join(
        [
            "📈 Growth",
            "",
            f"Всего приглашённых: {invited}",
            f"Активных реферальных бонусов: {rewarded}",
            f"Бонусов после оплаты: {paid_rewarded}",
            "",
            "Топ рефералов добавлю отдельным запросом, чтобы не рисковать self-join в проде.",
        ]
    )


def _config_text() -> str:
    return "\n".join(
        [
            "⚙️ Конфиг",
            "",
            f"APP_ENV: {settings.app_env}",
            f"PUBLIC_API_URL: {settings.public_api_url}",
            f"AI trial: {settings.ai_trial_request_limit}",
            f"AI basic/day: {settings.ai_basic_daily_request_limit}",
            f"OpenAI budget/month: ${settings.openai_monthly_budget_usd:.2f}",
            f"OpenAI alert remaining: ${settings.openai_remaining_alert_usd:.2f}",
            f"Alert interval: {settings.admin_alert_interval_seconds}s",
            f"Alert cooldown: {settings.admin_alert_cooldown_seconds}s",
            f"Premium trial days: {settings.premium_trial_days}",
            f"Referral reward days: {settings.referral_reward_days}",
            f"Admin IDs: {len(settings.admin_ids)}",
        ]
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


async def _broadcast_recipients(session, segment: str) -> list[int]:
    now = datetime.now(UTC)
    since_7d = now - timedelta(days=7)
    statement = select(User.telegram_id)
    if segment == "premium":
        statement = statement.where(User.subscription_expires_at > now)
    elif segment == "inactive_7":
        active_food = select(FoodEntry.user_id).where(FoodEntry.created_at >= since_7d)
        statement = statement.where(User.id.not_in(active_food))
    elif segment == "not_onboarded":
        statement = statement.where(User.onboarding_completed.is_(False))
    elif segment == "active_7":
        active_food = select(FoodEntry.user_id).where(FoodEntry.created_at >= since_7d)
        statement = statement.where(User.id.in_(active_food))
    result = await session.execute(statement.order_by(User.created_at.desc()).limit(5000))
    return [int(user_id) for user_id in result.scalars()]


async def _send_broadcast(recipients: list[int], text: str) -> int:
    if not settings.telegram_bot_token:
        return 0
    bot = Bot(settings.telegram_bot_token)
    sent = 0
    try:
        for user_id in recipients:
            try:
                await bot.send_message(user_id, text)
                sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                logger.info("Broadcast delivery failed user_id=%s", user_id, exc_info=True)
    finally:
        await bot.session.close()
    return sent


async def _send_user_message(user_id: int, text: str) -> bool:
    if not settings.telegram_bot_token:
        return False
    bot = Bot(settings.telegram_bot_token)
    try:
        await bot.send_message(user_id, text)
        return True
    except Exception:
        logger.info("Support reply delivery failed user_id=%s", user_id, exc_info=True)
        return False
    finally:
        await bot.session.close()


async def _scalar(session, statement) -> int:
    result = await session.execute(statement)
    value = result.scalar_one()
    return int(value or 0)


async def _api_ready_status() -> str:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get("http://api:3100/health/ready")
            response.raise_for_status()
            payload = response.json()
            checks = payload.get("checks", {})
            return f"ok database={checks.get('database')} redis={checks.get('redis')}"
    except Exception as exc:
        return f"ошибка: {type(exc).__name__}"


def _memory_info() -> str:
    try:
        values: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as file:
            for line in file:
                key, raw_value = line.split(":", 1)
                values[key] = int(raw_value.strip().split()[0]) * 1024
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", 0)
        used = max(total - available, 0)
        return f"{_format_bytes(used)} / {_format_bytes(total)}"
    except Exception:
        return "недоступно"


def _process_started_at() -> float:
    return ps_started_at


ps_started_at = time.time()


def _format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} TB"


def _format_seconds(value: float) -> str:
    seconds = int(max(value, 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}ч {minutes}м"
    if minutes:
        return f"{minutes}м {seconds}с"
    return f"{seconds}с"


def _today_bounds(tz: ZoneInfo) -> tuple[datetime, datetime]:
    now = datetime.now(tz)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def _parse_hhmm(value: str, fallback: str) -> tuple[int, int]:
    raw = value if ":" in value else fallback
    try:
        hour_text, minute_text = raw.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        hour_text, minute_text = fallback.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return _parse_hhmm(fallback, "09:05")
    return hour, minute


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
            "/today, /digest, /server, /openai, /alerts, /quality, /funnel, /promos, /user, /grant",
        ]
    )


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Дашборд", callback_data="admin:today"),
                InlineKeyboardButton(text="🖥 Сервер", callback_data="admin:server"),
            ],
            [
                InlineKeyboardButton(text="🧠 OpenAI", callback_data="admin:openai"),
                InlineKeyboardButton(text="🚨 Alerts", callback_data="admin:alerts"),
            ],
            [
                InlineKeyboardButton(text="📉 Quality", callback_data="admin:quality"),
            ],
            [
                InlineKeyboardButton(text="👥 CRM", callback_data="admin:crm"),
                InlineKeyboardButton(text="⚙️ Ops", callback_data="admin:ops"),
            ],
        ]
    )


def _today_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:today"),
                InlineKeyboardButton(text="🧠 OpenAI", callback_data="admin:openai"),
            ],
            [
                InlineKeyboardButton(text="🧭 Funnel", callback_data="admin:funnel"),
                InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu"),
            ],
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


def _ops_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🖥 Сервер", callback_data="admin:server"),
                InlineKeyboardButton(text="🧠 AI", callback_data="admin:ai"),
            ],
            [
                InlineKeyboardButton(text="💳 OpenAI costs", callback_data="admin:openai"),
                InlineKeyboardButton(text="🚨 Alerts", callback_data="admin:alerts"),
            ],
            [
                InlineKeyboardButton(text="📉 Quality", callback_data="admin:quality"),
            ],
            [
                InlineKeyboardButton(text="💰 Payments", callback_data="admin:payments"),
                InlineKeyboardButton(text="🎟 Promos", callback_data="admin:promos"),
            ],
            [InlineKeyboardButton(text="⚙️ Config", callback_data="admin:config")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _crm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👤 Пользователь", callback_data="admin:user:ask"),
                InlineKeyboardButton(text="💎 Premium", callback_data="admin:grant:ask"),
            ],
            [
                InlineKeyboardButton(text="🧭 Funnel", callback_data="admin:funnel"),
                InlineKeyboardButton(text="📈 Growth", callback_data="admin:growth"),
            ],
            [
                InlineKeyboardButton(text="📣 Broadcast", callback_data="admin:broadcast"),
                InlineKeyboardButton(text="💰 Payments", callback_data="admin:payments"),
            ],
            [InlineKeyboardButton(text="🎟 Promos", callback_data="admin:promos")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _server_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:server"),
                InlineKeyboardButton(text="🚨 Alerts", callback_data="admin:alerts"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _openai_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:openai"),
                InlineKeyboardButton(text="🧠 AI локально", callback_data="admin:ai"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _alerts_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:alerts"),
                InlineKeyboardButton(text="🖥 Сервер", callback_data="admin:server"),
            ],
            [InlineKeyboardButton(text="📉 Quality", callback_data="admin:quality")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _quality_keyboard(mode: str = "overview") -> InlineKeyboardMarkup:
    refresh_callback = "admin:quality" if mode == "overview" else f"admin:quality:{mode}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh_callback),
                InlineKeyboardButton(text="🚨 Alerts", callback_data="admin:alerts"),
            ],
            [
                InlineKeyboardButton(text="🙅 Не то", callback_data="admin:quality:not-it"),
                InlineKeyboardButton(text="🤖 AI", callback_data="admin:quality:ai"),
                InlineKeyboardButton(text="🔎 Поиск", callback_data="admin:quality:search"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _funnel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:funnel"),
                InlineKeyboardButton(text="📈 Growth", callback_data="admin:growth"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _payments_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:payments"),
                InlineKeyboardButton(text="👤 Пользователь", callback_data="admin:user:ask"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _promos_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:promos"),
                InlineKeyboardButton(text="➕ Создать", callback_data="admin:promos:create"),
            ],
            [InlineKeyboardButton(text="💰 Payments", callback_data="admin:payments")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _growth_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:growth"),
                InlineKeyboardButton(text="🧭 Funnel", callback_data="admin:funnel"),
            ],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


def _config_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:config"),
                InlineKeyboardButton(text="🖥 Сервер", callback_data="admin:server"),
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


def _broadcast_segment_keyboard(selected: str) -> InlineKeyboardMarkup:
    def label(segment: str, text: str) -> str:
        return ("✓ " if segment == selected else "") + text

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label("active_7", "Активные 7д"), callback_data="admin:broadcast:segment:active_7"),
                InlineKeyboardButton(text=label("premium", "Premium"), callback_data="admin:broadcast:segment:premium"),
            ],
            [
                InlineKeyboardButton(text=label("inactive_7", "Неактивные 7д"), callback_data="admin:broadcast:segment:inactive_7"),
                InlineKeyboardButton(text=label("not_onboarded", "Без onboarding"), callback_data="admin:broadcast:segment:not_onboarded"),
            ],
            [
                InlineKeyboardButton(text=label("all", "Все"), callback_data="admin:broadcast:segment:all"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")],
        ]
    )


def _broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить", callback_data="admin:broadcast:send")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")],
        ]
    )


def _broadcast_segment_title(segment: str) -> str:
    return {
        "active_7": "активные за 7 дней",
        "premium": "Premium",
        "inactive_7": "неактивные 7 дней",
        "not_onboarded": "не завершили onboarding",
        "all": "все пользователи",
    }.get(segment, segment)


def _cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")],
            [InlineKeyboardButton(text="🏠 Меню", callback_data="admin:menu")],
        ]
    )


if __name__ == "__main__":
    asyncio.run(main())
