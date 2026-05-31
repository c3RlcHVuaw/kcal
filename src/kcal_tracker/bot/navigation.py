from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from kcal_tracker.bot.keyboards import (
    MAIN_MENU_TEXTS,
    body_tools_keyboard,
    food_tools_keyboard,
    main_menu,
    more_menu_keyboard,
    progress_tools_keyboard,
    service_tools_keyboard,
)
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
@router.message(F.text.in_({"🏠 Меню", "Меню", "❌ Отмена", "Отмена"}))
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Вернулись в меню. Выбирай, что сделать дальше.", reply_markup=main_menu())


@router.message(F.text.in_({"☰ Ещё", "Ещё"}))
async def more_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.text == "Ещё":
        await message.answer("Обновил кнопки снизу.", reply_markup=main_menu())
    reply_markup = await _more_menu_markup(message.from_user.id, message.from_user.username)
    await message.answer("Что открыть?", reply_markup=reply_markup)


@router.callback_query(F.data == "nav:more")
async def more_menu_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    reply_markup = await _more_menu_markup(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text("Что открыть?", reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data.in_({"nav:food-tools", "nav:progress-tools", "nav:body-tools", "nav:service-tools"}))
async def show_more_section(callback: CallbackQuery) -> None:
    if callback.data == "nav:food-tools":
        reply_markup = await _food_tools_markup(callback.from_user.id, callback.from_user.username)
        await callback.message.edit_text("Еда: быстрые повторы и шаблоны.", reply_markup=reply_markup)
    elif callback.data == "nav:progress-tools":
        await callback.message.edit_text("Прогресс: день, неделя и месяц.", reply_markup=progress_tools_keyboard())
    elif callback.data == "nav:body-tools":
        await callback.message.edit_text("Тело: вода, активность и вес.", reply_markup=body_tools_keyboard())
    else:
        await callback.message.edit_text("Сервис: напоминания, настройки и подписка.", reply_markup=service_tools_keyboard())
    await callback.answer()


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


async def _food_tools_markup(telegram_id: int, username: str | None):
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(telegram_id, username)
        diary = DiaryService(session)
        frequent = await diary.frequent_foods(user)
        yesterday = await diary.entries_for_day_offset(user, days_ago=1)
    return food_tools_keyboard(
        has_frequent_foods=bool(frequent),
        has_yesterday_entries=bool(yesterday),
    )


def _should_reset_state(text: str) -> bool:
    if text in MAIN_MENU_TEXTS:
        return True
    return text.startswith("/start") or text.startswith("/cancel")
