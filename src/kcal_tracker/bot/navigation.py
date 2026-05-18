from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject

from kcal_tracker.bot.keyboards import MAIN_MENU_TEXTS, main_menu, more_menu_keyboard

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
    await message.answer("Ещё действия:", reply_markup=more_menu_keyboard())


def _should_reset_state(text: str) -> bool:
    if text in MAIN_MENU_TEXTS:
        return True
    return text.startswith("/start") or text.startswith("/cancel")
