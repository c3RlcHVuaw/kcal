from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot

from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.models import User
from kcal_tracker.services.growth import GrowthService
from kcal_tracker.services.subscriptions import SubscriptionService

logger = logging.getLogger(__name__)


async def yookassa_payment_loop(bot: Bot) -> None:
    while True:
        try:
            await _process_pending_yookassa_payments(bot)
        except Exception:
            logger.exception("Failed to process pending YooKassa payments")
        await asyncio.sleep(settings.yookassa_poll_interval_seconds)


async def _process_pending_yookassa_payments(bot: Bot) -> None:
    async with SessionLocal() as session:
        service = SubscriptionService(session)
        payments = await service.pending_yookassa_payments()
        for payment in payments:
            old_status = payment.status
            payment, until = await service.refresh_yookassa_payment(payment)
            user = await session.get(User, payment.user_id)
            if user is None:
                continue
            if until is not None:
                referrer = await GrowthService(session).reward_referrer_for_first_payment(user)
                await bot.send_message(
                    user.telegram_id,
                    f"Оплата прошла, AI открыт до {until:%d.%m.%Y}.",
                )
                if referrer is not None:
                    await bot.send_message(
                        referrer.telegram_id,
                        "Друг оформил подписку по твоей ссылке. Добавил тебе 7 дней AI.",
                    )
                continue
            if old_status == payment.status:
                continue
            if payment.status == "expired":
                await bot.send_message(
                    user.telegram_id,
                    "Счёт ЮKassa истёк: оплата не пришла в течение часа.",
                )
            elif payment.status in {"canceled", "failed"}:
                with suppress(Exception):
                    await bot.send_message(
                        user.telegram_id,
                        "Платёж ЮKassa отменён или завершился ошибкой. "
                        "Можно открыть подписку и попробовать другой способ.",
                    )
