from __future__ import annotations

import json
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from kcal_tracker.bot.keyboards import (
    subscription_bonuses_keyboard,
    subscription_keyboard,
    subscription_payment_method_keyboard,
)
from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.growth import GrowthService
from kcal_tracker.services.subscriptions import (
    SUBSCRIPTION_PAYLOAD,
    SUBSCRIPTION_PLAN_BASIC,
    YOOKASSA_PAYLOAD,
    PaymentConfigurationError,
    SubscriptionPlan,
    SubscriptionService,
    YooKassaPaymentError,
    subscription_plan,
    subscription_plans,
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
            "AI по фото, тексту и голосу на 30 дней.",
            (
                f"Старт: {settings.ai_subscription_rub} ₽, "
                f"{settings.ai_basic_daily_request_limit} AI-запросов в день."
            ),
            f"Безлимит: {settings.ai_unlimited_subscription_rub} ₽.",
            f"Звёзды Telegram дороже: от {settings.ai_subscription_stars} ⭐.",
            "За первого активного друга дадим 7 дней AI. "
            "За следующих — 7 дней после их первой оплаты.",
        ]
    )


@router.callback_query(F.data.startswith("subscription:stars") | (F.data == "subscription:buy"))
async def buy_subscription_with_stars(callback: CallbackQuery) -> None:
    plan = _plan_from_callback(callback.data, default=SUBSCRIPTION_PLAN_BASIC)
    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"AI в Kcal: {plan.title}",
        description="Распознавание еды по фото, тексту и голосу на 30 дней.",
        payload=f"{SUBSCRIPTION_PAYLOAD}:{plan.code}",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label=f"{plan.title} на {settings.ai_subscription_days} дней",
                amount=plan.stars,
            )
        ],
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:subscribe")
async def choose_subscription_payment(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "\n".join(
            [
                "Оформить подписку",
                "",
                f"Старт: {settings.ai_subscription_rub} ₽, "
                f"{settings.ai_basic_daily_request_limit} AI-запросов в день.",
                f"Безлимит: {settings.ai_unlimited_subscription_rub} ₽.",
                "Выбери способ оплаты:",
            ]
        ),
        reply_markup=subscription_payment_method_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:bonuses")
async def show_subscription_bonuses(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "\n".join(
            [
                "Бонусы",
                "",
                "Здесь лежат разовые предложения: пробный premium-день и возврат AI на день.",
            ]
        ),
        reply_markup=subscription_bonuses_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("subscription:yookassa:"))
async def buy_subscription_with_yookassa(callback: CallbackQuery) -> None:
    plan, method = _payment_choice_from_callback(callback.data)
    if settings.yookassa_provider_token:
        await _send_yookassa_invoice(callback, plan.code, method)
        return

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        try:
            payment = await SubscriptionService(session).create_yookassa_payment(
                user,
                method,
                plan.code,
            )
        except PaymentConfigurationError:
            await callback.answer(
                "ЮKassa ещё не настроена на сервере: нужен YOOKASSA_PROVIDER_TOKEN "
                "или YOOKASSA_SHOP_ID/YOOKASSA_SECRET_KEY.",
                show_alert=True,
            )
            return
        except YooKassaPaymentError as exc:
            await callback.answer(str(exc), show_alert=True)
            return

    method_text = "картой" if method == "bank_card" else "через СБП"
    await callback.message.answer(
        "\n".join(
            [
                f"Счёт на оплату тарифа «{plan.title}» {method_text} готов.",
                f"Сумма: {plan.rub} ₽.",
                "После оплаты я сам проверю статус и открою AI.",
                "Если не оплатить в течение часа, счёт истечёт.",
            ]
        ),
        reply_markup=_yookassa_payment_keyboard(payment.id, payment.confirmation_url),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("subscription:check:"))
async def check_yookassa_payment(callback: CallbackQuery) -> None:
    payment_id = int(callback.data.rsplit(":", 1)[-1])
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        service = SubscriptionService(session)
        payment = await service.get_payment_for_user(payment_id, user)
        if payment is None:
            await callback.answer("Не нашёл этот платёж.", show_alert=True)
            return
        payment, until = await service.refresh_yookassa_payment(payment)
        referrer = (
            await GrowthService(session).reward_referrer_for_first_payment(user)
            if until
            else None
        )

    if until is not None:
        await callback.message.answer(
            f"Готово, AI открыт до {until:%d.%m.%Y}.",
            reply_markup=subscription_keyboard(),
        )
        if referrer is not None:
            await callback.bot.send_message(
                referrer.telegram_id,
                "Друг оформил подписку по твоей ссылке. Добавил тебе 7 дней AI.",
            )
        await callback.answer("Оплата прошла.")
        return
    if payment.status == "expired":
        await callback.answer("Счёт истёк: оплата не пришла в течение часа.", show_alert=True)
        return
    if payment.status in {"canceled", "failed"}:
        await callback.answer("Платёж отменён или завершился ошибкой.", show_alert=True)
        return
    await callback.answer("Пока не вижу оплату. Если уже оплатил, попробуй ещё раз через минуту.")


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    payload = pre_checkout_query.invoice_payload
    if payload == SUBSCRIPTION_PAYLOAD or payload.startswith(f"{SUBSCRIPTION_PAYLOAD}:"):
        await pre_checkout_query.answer(ok=True)
        return
    if not payload.startswith(f"{YOOKASSA_PAYLOAD}:"):
        await pre_checkout_query.answer(ok=False, error_message="Не получилось проверить платёж.")
        return
    payment_id = _payment_id_from_yookassa_payload(payload)
    if payment_id is None:
        await pre_checkout_query.answer(ok=False, error_message="Не получилось проверить платёж.")
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            pre_checkout_query.from_user.id,
            pre_checkout_query.from_user.username,
        )
        payment = await SubscriptionService(session).get_payment_for_user(payment_id, user)
        if payment is None:
            await pre_checkout_query.answer(ok=False, error_message="Счёт не найден.")
            return
        if payment.expires_at is not None and payment.expires_at <= datetime.now(UTC):
            payment.status = "expired"
            payment.last_error = "Платёж не был оплачен за отведённое время."
            await session.commit()
            await pre_checkout_query.answer(ok=False, error_message="Счёт уже истёк.")
            return
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    payment = message.successful_payment
    if payment.invoice_payload.startswith(f"{YOOKASSA_PAYLOAD}:"):
        await _handle_successful_yookassa_invoice(message)
        return
    if payment.invoice_payload != SUBSCRIPTION_PAYLOAD:
        await message.answer("Платёж получен, но назначение не распознано. Напиши в поддержку.")
        return
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
        referrer = await GrowthService(session).reward_referrer_for_first_payment(user)
    await message.answer(
        f"Готово, AI открыт до {until:%d.%m.%Y}.",
        reply_markup=subscription_keyboard(),
    )
    if referrer is not None:
        await message.bot.send_message(
            referrer.telegram_id,
            "Друг оформил подписку по твоей ссылке. Добавил тебе 7 дней AI.",
        )


@router.callback_query(F.data == "subscription:trial")
async def activate_premium_trial(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        until = await GrowthService(session).grant_premium_trial(user)

    if until is None:
        await callback.answer(
            "Пробный premium-день уже использован или AI уже активен.",
            show_alert=True,
        )
        return
    await callback.message.edit_text(
        f"Готово, пробный premium-день включён до {until:%d.%m.%Y %H:%M} UTC.",
        reply_markup=subscription_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:winback")
async def activate_winback_offer(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        until = await GrowthService(session).grant_winback_offer(user)

    if until is None:
        await callback.answer(
            "Этот бонус доступен один раз после окончания подписки.",
            show_alert=True,
        )
        return
    await callback.message.edit_text(
        f"Вернул AI на день — доступ открыт до {until:%d.%m.%Y %H:%M} UTC.",
        reply_markup=subscription_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:referral")
async def show_referral_link(callback: CallbackQuery) -> None:
    bot = await callback.bot.me()
    if bot.username is None:
        await callback.answer("Не смог собрать ссылку для этого бота.", show_alert=True)
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        link = await GrowthService(session).referral_link(user, bot.username)

    await callback.message.edit_text(
        "\n".join(
            [
                "Твоя ссылка для друзей:",
                link,
                "",
                "Друг сразу получит 1 premium-день. "
                "Тебе добавится 7 дней AI, когда первый друг будет активен 5 дней из 7.",
                "За следующих друзей бонус начисляется после их первой оплаты.",
            ]
        ),
        reply_markup=subscription_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:referral-dashboard")
async def show_referral_dashboard(callback: CallbackQuery) -> None:
    bot = await callback.bot.me()
    if bot.username is None:
        await callback.answer("Не смог собрать ссылку для этого бота.", show_alert=True)
        return
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        dashboard = await GrowthService(session).referral_dashboard(user, bot.username)

    lines = [
        "Реферальный кабинет",
        "",
        f"Пришло друзей: {dashboard.invited_count}",
        (
            "Первый активный бонус: уже начислен"
            if dashboard.first_active_reward_used
            else "Первый активный бонус: ждём друга с 5 активными днями из 7"
        ),
        "",
        "Ссылка:",
        dashboard.link,
    ]
    if dashboard.friends:
        lines.extend(["", "Друзья:"])
        for index, friend in enumerate(dashboard.friends, start=1):
            status = (
                "бонус начислен"
                if friend.active_rewarded or friend.payment_rewarded
                else "в процессе"
            )
            lines.append(
                f"#{index}: {friend.active_days}/{friend.required_days} активных дней, {status}"
            )
    else:
        lines.extend(["", "Пока никто не пришёл по ссылке."])

    await callback.message.edit_text("\n".join(lines), reply_markup=subscription_keyboard())
    await callback.answer()


def _yookassa_payment_keyboard(
    payment_id: int,
    confirmation_url: str | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if confirmation_url:
        rows.append([InlineKeyboardButton(text="Перейти к оплате в ЮKassa", url=confirmation_url)])
    rows.append(
        [
            InlineKeyboardButton(
                text="Проверить оплату",
                callback_data=f"subscription:check:{payment_id}",
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="Вернуться к подписке", callback_data="subscription:open")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_yookassa_invoice(callback: CallbackQuery, plan_code: str, method: str) -> None:
    plan = subscription_plan(plan_code)
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        try:
            payment = await SubscriptionService(session).create_yookassa_invoice_attempt(
                user,
                method,
                plan.code,
            )
        except PaymentConfigurationError:
            await callback.answer("ЮKassa ещё не настроена на сервере.", show_alert=True)
            return

    method_text = "Карта" if method == "bank_card" else "СБП"
    provider_data = json.dumps(
        {
            "payment_method_data": {"type": method},
            "metadata": {
                "payment_id": str(payment.id),
                "telegram_id": str(callback.from_user.id),
                "plan": plan.code,
            },
        },
        ensure_ascii=False,
    )
    try:
        await callback.bot.send_invoice(
            chat_id=callback.message.chat.id,
            title=f"AI в Kcal: {plan.title}, {method_text}",
            description="Распознавание еды по фото, тексту и голосу на 30 дней.",
            payload=f"{YOOKASSA_PAYLOAD}:{plan.code}:{method}:{payment.id}",
            provider_token=settings.yookassa_provider_token,
            currency="RUB",
            prices=[
                LabeledPrice(
                    label=f"{plan.title} на {settings.ai_subscription_days} дней",
                    amount=plan.rub * 100,
                )
            ],
            provider_data=provider_data,
        )
    except TelegramBadRequest as exc:
        if "PAYMENT_PROVIDER_INVALID" in str(exc):
            await callback.answer(
                "ЮKassa отклонила токен платежей. Нужен provider token из BotFather "
                "для этого бота, не API-ключ ЮKassa.",
                show_alert=True,
            )
            return
        raise
    await callback.answer()


async def _handle_successful_yookassa_invoice(message: Message) -> None:
    successful_payment = message.successful_payment
    payment_id = _payment_id_from_yookassa_payload(successful_payment.invoice_payload)
    if payment_id is None:
        await message.answer("Платёж получен, но счёт не распознан. Напиши в поддержку.")
        return

    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            message.from_user.id,
            message.from_user.username,
        )
        service = SubscriptionService(session)
        payment = await service.get_payment_for_user(payment_id, user)
        if payment is None:
            await message.answer("Платёж получен, но счёт не найден. Напиши в поддержку.")
            return
        until = await service.activate_from_yookassa_invoice_payment(
            payment=payment,
            telegram_payment_charge_id=successful_payment.telegram_payment_charge_id,
            provider_payment_charge_id=successful_payment.provider_payment_charge_id,
        )
        referrer = await GrowthService(session).reward_referrer_for_first_payment(user)

    await message.answer(
        f"Готово, AI открыт до {until:%d.%m.%Y}.",
        reply_markup=subscription_keyboard(),
    )
    if referrer is not None:
        await message.bot.send_message(
            referrer.telegram_id,
            "Друг оформил подписку по твоей ссылке. Добавил тебе 7 дней AI.",
        )


def _payment_id_from_yookassa_payload(payload: str) -> int | None:
    parts = payload.split(":")
    if len(parts) == 3 and parts[0] == YOOKASSA_PAYLOAD:
        payment_id = parts[2]
    elif len(parts) == 4 and parts[0] == YOOKASSA_PAYLOAD:
        payment_id = parts[3]
    else:
        return None
    try:
        return int(payment_id)
    except ValueError:
        return None


def _payment_choice_from_callback(data: str) -> tuple[SubscriptionPlan, str]:
    parts = data.split(":")
    if len(parts) == 3:
        return subscription_plan(SUBSCRIPTION_PLAN_BASIC), parts[2]
    if len(parts) == 4:
        return subscription_plan(parts[2]), parts[3]
    return subscription_plan(SUBSCRIPTION_PLAN_BASIC), "sbp"


def _plan_from_callback(data: str, *, default: str) -> SubscriptionPlan:
    parts = data.split(":")
    if len(parts) >= 3 and parts[2] in subscription_plans():
        return subscription_plan(parts[2])
    return subscription_plan(default)
