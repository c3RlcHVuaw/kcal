from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from kcal_tracker.bot.keyboards import language_keyboard, main_menu
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.growth import GrowthService
from kcal_tracker.services.users import UserService

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
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
