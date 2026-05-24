from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from kcal_tracker.bot.keyboards import main_menu
from kcal_tracker.services.admin_notifications import notify_admins, support_reply_keyboard

router = Router()


class SupportFlow(StatesGroup):
    waiting_message = State()


@router.message(F.text.in_({"/support", "🆘 Поддержка", "Поддержка", "поддержка"}))
async def ask_support_message(message: Message, state: FSMContext) -> None:
    await state.set_state(SupportFlow.waiting_message)
    await message.answer(
        "Напиши сообщение для поддержки одним текстом. Я передам его админам.",
        reply_markup=main_menu(),
    )


@router.callback_query(F.data == "support:open")
async def ask_support_message_inline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportFlow.waiting_message)
    await callback.message.edit_text(
        "Напиши сообщение для поддержки одним текстом. Я передам его админам."
    )
    await callback.answer()


@router.message(SupportFlow.waiting_message, F.text)
async def send_support_message(message: Message, state: FSMContext) -> None:
    text = " ".join((message.text or "").split())
    if not text:
        await message.answer("Сообщение пустое. Напиши, что случилось.")
        return

    user = message.from_user
    username = f"@{user.username}" if user and user.username else "-"
    user_id = user.id if user else 0
    await notify_admins(
        "\n".join(
            [
                "🆘 Новое обращение в поддержку",
                "",
                f"User ID: {user_id}",
                f"Username: {username}",
                "",
                text,
            ]
        ),
        reply_markup=support_reply_keyboard(user_id),
    )
    await state.clear()
    await message.answer(
        "Передал в поддержку. Ответ придёт сюда от бота.",
        reply_markup=main_menu(),
    )
