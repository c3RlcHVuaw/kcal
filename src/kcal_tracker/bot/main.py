from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from kcal_tracker.bot.handlers import diary, food, payments, profile, start
from kcal_tracker.bot.navigation import MenuStateResetMiddleware
from kcal_tracker.bot.navigation import router as navigation_router
from kcal_tracker.config import settings
from kcal_tracker.services.payment_monitor import yookassa_payment_loop
from kcal_tracker.services.reminders import reminder_loop


async def main() -> None:
    logging.basicConfig(level=settings.log_level)
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    redis = Redis.from_url(settings.redis_url)
    bot = Bot(settings.telegram_bot_token)
    dispatcher = Dispatcher(storage=RedisStorage(redis=redis))
    dispatcher.message.middleware(MenuStateResetMiddleware())
    dispatcher.include_router(navigation_router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(profile.router)
    dispatcher.include_router(payments.router)
    dispatcher.include_router(diary.router)
    dispatcher.include_router(food.router)
    reminders = asyncio.create_task(reminder_loop(bot))
    yookassa_payments = asyncio.create_task(yookassa_payment_loop(bot))
    try:
        await dispatcher.start_polling(bot)
    finally:
        reminders.cancel()
        yookassa_payments.cancel()
        with suppress(asyncio.CancelledError):
            await reminders
        with suppress(asyncio.CancelledError):
            await yookassa_payments


if __name__ == "__main__":
    asyncio.run(main())
