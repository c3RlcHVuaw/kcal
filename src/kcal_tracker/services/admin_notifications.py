from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from kcal_tracker.config import settings

logger = logging.getLogger(__name__)


async def notify_admins(text: str, *, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    if not settings.admin_bot_token or not settings.admin_ids:
        return

    bot = Bot(settings.admin_bot_token)
    try:
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(admin_id, text, reply_markup=reply_markup)
            except Exception:
                logger.warning("Failed to notify admin_id=%s", admin_id, exc_info=True)
    finally:
        await bot.session.close()


def support_reply_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ответить", callback_data=f"admin:support:reply:{user_id}")],
        ]
    )
