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
from kcal_tracker.services.throttle import reserve_auto_message

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
                await _send_guarded_payment_message(
                    bot,
                    user,
                    f"payment_success:{payment.id}",
                    f"Оплата прошла, AI открыт до {until:%d.%m.%Y}.",
                )
                if referrer is not None:
                    await _send_guarded_payment_message(
                        bot,
                        referrer,
                        f"referral_reward:{payment.id}",
                        "Друг оформил подписку по твоей ссылке. Добавил тебе 7 дней AI.",
                    )
                continue
            if old_status == payment.status:
                continue
            if payment.status == "expired":
                await _send_guarded_payment_message(
                    bot,
                    user,
                    f"payment_expired:{payment.id}",
                    "Счёт ЮKassa истёк: оплата не пришла в течение часа.",
                )
            elif payment.status in {"canceled", "failed"}:
                with suppress(Exception):
                    await _send_guarded_payment_message(
                        bot,
                        user,
                        f"payment_failed:{payment.id}",
                        "Платёж ЮKassa отменён или завершился ошибкой. "
                        "Можно открыть подписку и попробовать другой способ.",
                    )


async def _send_guarded_payment_message(bot: Bot, user: User, message_type: str, text: str) -> bool:
    if not await reserve_auto_message(user.id, message_type, window_seconds=7 * 24 * 60 * 60):
        logger.info("Skipped duplicate payment message type=%s user_id=%s", message_type, user.id)
        return False
    await bot.send_message(user.telegram_id, text)
    return True
