from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from kcal_tracker.bot.handlers.diary import _reminders_view
from kcal_tracker.bot.handlers.payments import _subscription_view
from kcal_tracker.bot.handlers.support import SupportFlow
from kcal_tracker.bot.keyboards import (
    language_keyboard,
    main_menu,
    subscription_payment_method_keyboard,
)
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.growth import GrowthService
from kcal_tracker.services.subscriptions import (
    SUBSCRIPTION_PLAN_BASIC,
    subscription_plan,
    subscription_plans,
)
from kcal_tracker.services.users import UserService

router = Router()


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    start_payload = _start_payload(message.text)
    async with SessionLocal() as session:
        users = UserService(session)
        existing_user = await users.get_by_telegram_id(message.from_user.id)
        user = await users.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
        if existing_user is None:
            await GrowthService(session).apply_referral_start(user, start_payload)
    if not user.onboarding_completed:
        await message.answer(
            "Привет. За минуту настроим дневник под тебя. Сначала выбери язык.",
            reply_markup=language_keyboard(),
        )
        return
    if start_payload == "subscription":
        text, reply_markup = await _subscription_view(message.from_user.id, message.from_user.username)
        await message.answer(text, reply_markup=reply_markup)
        return
    if start_payload in {"subscription_basic", "subscription_unlimited"}:
        plan_code = start_payload.removeprefix("subscription_")
        await message.answer(
            _subscription_plan_text(plan_code),
            reply_markup=subscription_payment_method_keyboard(plan_code),
        )
        return
    if start_payload and start_payload.startswith("subscription_"):
        plan_code, method = _subscription_payment_payload(start_payload)
        if plan_code is not None and method is not None:
            await message.answer(
                _subscription_payment_text(plan_code, method),
                reply_markup=subscription_payment_method_keyboard(plan_code),
            )
            return
    if start_payload == "reminders":
        text, reply_markup = await _reminders_view(message.from_user.id, message.from_user.username)
        await message.answer(text, reply_markup=reply_markup)
        return
    if start_payload == "support":
        await state.set_state(SupportFlow.waiting_message)
        await message.answer(
            "Напиши сообщение для поддержки одним текстом. Я передам его админам.",
            reply_markup=main_menu(),
        )
        return
    await message.answer("Я на месте. Что запишем?", reply_markup=main_menu())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(_help_text(), reply_markup=main_menu())


def _help_text() -> str:
    return "\n".join(
        [
            "Что можно сделать:",
            "",
            "➕ Еда — написать приём пищи, прислать фото блюда или штрихкод.",
            "📊 Сегодня — посмотреть дневник, воду, БЖУ и остаток до цели.",
            "☰ Ещё — любимое, частое, неделя, вес, напоминания и настройки.",
            "",
            "Во время ввода можно нажать «❌ Отмена» или написать /cancel.",
        ]
    )


def _start_payload(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    return parts[1]


def _subscription_payment_payload(payload: str) -> tuple[str | None, str | None]:
    parts = payload.split("_")
    if len(parts) != 3 or parts[0] != "subscription":
        return None, None
    plan_code, method = parts[1], parts[2]
    if plan_code not in subscription_plans() or method not in {"sbp", "auto", "stars"}:
        return None, None
    return plan_code, method


def _subscription_plan_text(plan_code: str) -> str:
    plan = subscription_plan(plan_code)
    limit = "без дневного лимита" if plan.daily_limit is None else f"{plan.daily_limit} AI-запросов в день"
    return "\n".join(
        [
            f"Тариф «{plan.title}»",
            "",
            f"30 дней, {limit}.",
            f"Цена: {plan.rub} ₽ или {plan.stars} ⭐.",
            "",
            "Выберите способ оплаты ниже.",
        ]
    )


def _subscription_payment_text(plan_code: str, method: str) -> str:
    plan = subscription_plan(plan_code or SUBSCRIPTION_PLAN_BASIC)
    method_text = {
        "sbp": "СБП",
        "auto": "Карта/SberPay",
        "stars": "Звёзды Telegram",
    }[method]
    return "\n".join(
        [
            f"Подключение «{plan.title}»",
            "",
            f"Вы выбрали {method_text}. Нажмите кнопку ниже, чтобы создать счёт.",
        ]
    )
