from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from kcal_tracker.bot.handlers.diary import _reminders_view
from kcal_tracker.bot.handlers.payments import _subscription_view
from kcal_tracker.bot.handlers.support import SupportFlow
from kcal_tracker.bot.keyboards import language_keyboard, main_menu
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.growth import GrowthService
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
