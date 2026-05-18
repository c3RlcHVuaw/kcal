from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from kcal_tracker.bot.keyboards import language_keyboard, main_menu
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.users import UserService

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
        )
    if not user.onboarding_completed:
        await message.answer(
            "Давай настроим дневник. Выбери язык.",
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
            "📷 Фото — распознать блюдо или продукт по штрихкоду.",
            "✍️ Еда — написать приём пищи обычным текстом.",
            "📊 Сегодня — посмотреть дневник, воду и БЖУ за день.",
            "🔥 Остаток — понять, сколько осталось до цели.",
            "☰ Ещё — любимое, частое, неделя, вес, напоминания и настройки.",
            "",
            "Во время ввода можно нажать «❌ Отмена» или написать /cancel.",
        ]
    )
