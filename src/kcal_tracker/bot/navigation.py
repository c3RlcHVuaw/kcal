from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

from kcal_tracker.bot.keyboards import MAIN_MENU_TEXTS, main_menu, more_menu_keyboard
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.diary import DiaryService
from kcal_tracker.services.users import UserService

router = Router()


class MenuStateResetMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.text:
            state: FSMContext | None = data.get("state")
            if state is not None and _should_reset_state(event.text):
                await state.clear()
        return await handler(event, data)


@router.message(Command("cancel"))
@router.message(F.text.in_({"🏠 Меню", "❌ Отмена"}))
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Вернулись в меню. Выбирай, что сделать дальше.", reply_markup=main_menu())


@router.message(F.text == "☰ Ещё")
async def more_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    reply_markup = await _more_menu_markup(message.from_user.id, message.from_user.username)
    await message.answer("Ещё действия:", reply_markup=reply_markup)


async def _more_menu_markup(telegram_id: int, username: str | None):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(telegram_id, username)
        diary = DiaryService(session)
        frequent = await diary.frequent_foods(user)
        yesterday = await diary.entries_for_day_offset(user, days_ago=1)
    return more_menu_keyboard(
        has_frequent_foods=bool(frequent),
        has_yesterday_entries=bool(yesterday),
    )


def _should_reset_state(text: str) -> bool:
    if text in MAIN_MENU_TEXTS:
        return True
    return text.startswith("/start") or text.startswith("/cancel")
