from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from kcal_tracker.bot.keyboards import subscription_keyboard
from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.subscriptions import (
    SUBSCRIPTION_PAYLOAD,
    SubscriptionService,
    subscription_until_text,
)
from kcal_tracker.services.users import UserService

router = Router()


@router.message(F.text == "💎 Подписка")
async def subscription_menu(message: Message) -> None:
    text = await _subscription_text(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=subscription_keyboard())


@router.callback_query(F.data == "subscription:open")
async def subscription_menu_inline(callback: CallbackQuery) -> None:
    text = await _subscription_text(callback.from_user.id, callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=subscription_keyboard())
    await callback.answer()


async def _subscription_text(telegram_id: int, username: str | None) -> str:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        text = subscription_until_text(user)

    return "\n".join(
        [
            text,
            "",
            "Можно попробовать AI бесплатно: 3 запроса до подписки.",
            f"AI по фото, тексту и голосу: {settings.ai_subscription_stars} ⭐ на 30 дней.",
        ]
    )


@router.callback_query(F.data == "subscription:buy")
async def buy_subscription(callback: CallbackQuery) -> None:
    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="AI в Kcal",
        description="Распознавание еды по фото, тексту и голосу на 30 дней.",
        payload=SUBSCRIPTION_PAYLOAD,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="AI на 30 дней", amount=settings.ai_subscription_stars)],
    )
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    if pre_checkout_query.invoice_payload != SUBSCRIPTION_PAYLOAD:
        await pre_checkout_query.answer(ok=False, error_message="Не получилось проверить платёж.")
        return
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    payment = message.successful_payment
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        until = await SubscriptionService(session).activate_from_stars_payment(
            user=user,
            amount_stars=payment.total_amount,
            payload=payment.invoice_payload,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            provider_payment_charge_id=payment.provider_payment_charge_id,
        )
    await message.answer(f"Готово, AI открыт до {until:%d.%m.%Y}.")
