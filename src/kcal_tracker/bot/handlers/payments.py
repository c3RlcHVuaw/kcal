from __future__ import annotations

import json
from dataclasses import dataclass
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
    subscription_plan_keyboard,
)
from kcal_tracker.config import settings
from kcal_tracker.database import SessionLocal
from kcal_tracker.services.growth import GrowthService
from kcal_tracker.services.subscriptions import (
    SUBSCRIPTION_PAYLOAD,
    SUBSCRIPTION_PLAN_BASIC,
    YOOKASSA_FORCED_PAYMENT_METHODS,
    YOOKASSA_PAYLOAD,
    YOOKASSA_PAYMENT_METHOD_AUTO,
    PaymentConfigurationError,
    SubscriptionPlan,
    SubscriptionService,
    YooKassaPaymentError,
    YooKassaRefundError,
    has_active_subscription,
    subscription_plan,
    subscription_plans,
    subscription_until_text,
)
from kcal_tracker.services.users import UserService

router = Router()


@dataclass(frozen=True)
class SubscriptionActionFlags:
    trial_available: bool
    winback_available: bool
    refund_available: bool

    @property
    def any_bonus(self) -> bool:
        return self.trial_available or self.winback_available or self.refund_available


@router.message(F.text == "💎 Подписка")
async def subscription_menu(message: Message) -> None:
    text, reply_markup = await _subscription_view(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "subscription:open")
async def subscription_menu_inline(callback: CallbackQuery) -> None:
    text, reply_markup = await _subscription_view(
        callback.from_user.id,
        callback.from_user.username,
    )
    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


async def _subscription_view(
    telegram_id: int,
    username: str | None,
) -> tuple[str, InlineKeyboardMarkup]:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            telegram_id,
            username,
        )
        text = subscription_until_text(user)
        active = has_active_subscription(user)
        flags = await _subscription_action_flags(session, user)

    return (
        "\n".join(
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
        ),
        subscription_keyboard(active=active, bonuses_available=flags.any_bonus),
    )


async def _subscription_markup_for_user(
    telegram_id: int,
    username: str | None,
) -> InlineKeyboardMarkup:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(telegram_id, username)
        flags = await _subscription_action_flags(session, user)
        return subscription_keyboard(
            active=has_active_subscription(user),
            bonuses_available=flags.any_bonus,
        )


async def _subscription_action_flags(session, user) -> SubscriptionActionFlags:
    active = has_active_subscription(user)
    refund_available = (
        await SubscriptionService(session).latest_refundable_payment(user) is not None
    )
    return SubscriptionActionFlags(
        trial_available=(
            settings.premium_trial_days > 0
            and user.premium_trial_used_at is None
            and not active
        ),
        winback_available=(
            settings.winback_offer_days > 0
            and user.winback_used_at is None
            and not active
            and user.subscription_expires_at is not None
        ),
        refund_available=refund_available,
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
async def choose_subscription_plan(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "\n".join(
            [
                "Выбери тариф",
                "",
                f"Старт: {settings.ai_subscription_rub} ₽, "
                f"{settings.ai_basic_daily_request_limit} AI-запросов в день.",
                f"Безлимит: {settings.ai_unlimited_subscription_rub} ₽.",
            ]
        ),
        reply_markup=subscription_plan_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("subscription:plan:"))
async def choose_subscription_payment(callback: CallbackQuery) -> None:
    plan = _plan_from_callback(callback.data, default=SUBSCRIPTION_PLAN_BASIC)
    limit_text = (
        "без дневного лимита"
        if plan.daily_limit is None
        else f"{plan.daily_limit} AI-запросов в день"
    )
    await callback.message.edit_text(
        "\n".join(
            [
                f"Тариф «{plan.title}»",
                "",
                f"30 дней, {limit_text}.",
                f"Цена: {plan.rub} ₽ или {plan.stars} ⭐.",
                "",
                "СБП откроется на странице YooKassa с QR-кодом или выбором банка.",
                "Карта/SberPay откроется встроенной оплатой Telegram.",
            ]
        ),
        reply_markup=subscription_payment_method_keyboard(plan.code),
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:bonuses")
async def show_subscription_bonuses(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        flags = await _subscription_action_flags(session, user)
    lines = [
        "Бонусы",
        "",
        (
            "Доступные действия по подписке:"
            if flags.any_bonus
            else "Сейчас нет доступных бонусов или возврата."
        ),
    ]
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=subscription_bonuses_keyboard(
            trial_available=flags.trial_available,
            winback_available=flags.winback_available,
            refund_available=flags.refund_available,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:refund")
async def show_refund_info(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "\n".join(
            [
                "Возврат оплаты",
                "",
                "Автоматический возврат доступен для последней успешной оплаты за 24 часа.",
                "После возврата 30 дней AI будут сняты с подписки.",
                "",
                "Продолжить?",
            ]
        ),
        reply_markup=_refund_confirmation_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "subscription:refund:confirm")
async def confirm_refund(callback: CallbackQuery) -> None:
    async with SessionLocal() as session:
        user = await UserService(session).get_or_create(
            callback.from_user.id,
            callback.from_user.username,
        )
        service = SubscriptionService(session)
        payment = await service.latest_refundable_payment(user)
        if payment is None:
            await callback.answer(
                "Не нашёл успешную оплату за последние 24 часа.",
                show_alert=True,
            )
            return
        if payment.method == "stars":
            if not payment.telegram_payment_charge_id:
                await callback.answer("Не нашёл номер платежа Stars.", show_alert=True)
                return
            try:
                await callback.bot.refund_star_payment(
                    user_id=callback.from_user.id,
                    telegram_payment_charge_id=payment.telegram_payment_charge_id,
                )
            except TelegramBadRequest as exc:
                await callback.answer(
                    f"Telegram не принял возврат Stars: {exc.message}",
                    show_alert=True,
                )
                return
            await service.mark_payment_refunded(payment)
            await session.refresh(user)
            until = user.subscription_expires_at
            refund_status = "succeeded"
        else:
            try:
                refund = await service.refund_yookassa_payment(payment)
            except PaymentConfigurationError:
                await callback.answer(
                    "Возврат через YooKassa ещё не настроен: нужен shop id и secret key.",
                    show_alert=True,
                )
                return
            except YooKassaRefundError as exc:
                await callback.answer(_payment_error_message(str(exc)), show_alert=True)
                return
            until = refund.subscription_expires_at
            refund_status = refund.status

    if refund_status == "succeeded":
        reply_markup = await _subscription_markup_for_user(
            callback.from_user.id,
            callback.from_user.username,
        )
        await callback.message.edit_text(
            "\n".join(
                [
                    "Возврат оформлен.",
                    _subscription_after_refund_text(until),
                ]
            ),
            reply_markup=reply_markup,
        )
    else:
        reply_markup = await _subscription_markup_for_user(
            callback.from_user.id,
            callback.from_user.username,
        )
        await callback.message.edit_text(
            "Возврат создан и ещё обрабатывается. Если статус не обновится, напиши в поддержку.",
            reply_markup=reply_markup,
        )
    await callback.answer("Готово.")


@router.callback_query(F.data.startswith("subscription:yookassa:"))
async def buy_subscription_with_yookassa(callback: CallbackQuery) -> None:
    plan, method = _payment_choice_from_callback(callback.data)
    if settings.yookassa_provider_token and method != "sbp":
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
            await callback.answer(_payment_error_message(str(exc)), show_alert=True)
            return

    method_text = _yookassa_method_text(method)
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
        reply_markup = await _subscription_markup_for_user(
            callback.from_user.id,
            callback.from_user.username,
        )
        await callback.message.answer(
            f"Готово, AI открыт до {until:%d.%m.%Y}.",
            reply_markup=reply_markup,
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
    if not (
        payment.invoice_payload == SUBSCRIPTION_PAYLOAD
        or payment.invoice_payload.startswith(f"{SUBSCRIPTION_PAYLOAD}:")
    ):
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
    reply_markup = await _subscription_markup_for_user(
        message.from_user.id,
        message.from_user.username,
    )
    await message.answer(
        f"Готово, AI открыт до {until:%d.%m.%Y}.",
        reply_markup=reply_markup,
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
    reply_markup = await _subscription_markup_for_user(
        callback.from_user.id,
        callback.from_user.username,
    )
    await callback.message.edit_text(
        f"Готово, пробный premium-день включён до {until:%d.%m.%Y %H:%M} UTC.",
        reply_markup=reply_markup,
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
    reply_markup = await _subscription_markup_for_user(
        callback.from_user.id,
        callback.from_user.username,
    )
    await callback.message.edit_text(
        f"Вернул AI на день — доступ открыт до {until:%d.%m.%Y %H:%M} UTC.",
        reply_markup=reply_markup,
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

    reply_markup = await _subscription_markup_for_user(
        callback.from_user.id,
        callback.from_user.username,
    )
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
        reply_markup=reply_markup,
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

    reply_markup = await _subscription_markup_for_user(
        callback.from_user.id,
        callback.from_user.username,
    )
    await callback.message.edit_text("\n".join(lines), reply_markup=reply_markup)
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


def _refund_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить возврат",
                    callback_data="subscription:refund:confirm",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="subscription:bonuses")],
        ]
    )


def _subscription_after_refund_text(until: datetime | None) -> str:
    if until is None or until <= datetime.now(UTC):
        return "AI-подписка сейчас не активна."
    return f"AI открыт до {until:%d.%m.%Y}."


def _payment_error_message(message: str) -> str:
    lowered = message.lower()
    if "shopid or secret key" in lowered or ("shopid" in lowered and "secret key" in lowered):
        return (
            "СБП через YooKassa пока не настроен: нужен правильный ShopID "
            "из личного кабинета YooKassa и secret key от этого же магазина."
        )
    return message


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

    provider_payload: dict[str, object] = {
        "metadata": {
            "payment_id": str(payment.id),
            "telegram_id": str(callback.from_user.id),
            "plan": plan.code,
        },
    }
    if method in YOOKASSA_FORCED_PAYMENT_METHODS:
        provider_payload["payment_method_data"] = {"type": method}
    provider_data = json.dumps(provider_payload, ensure_ascii=False)
    try:
        await callback.bot.send_invoice(
            chat_id=callback.message.chat.id,
            title=_yookassa_invoice_title(plan, method),
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

    reply_markup = await _subscription_markup_for_user(
        message.from_user.id,
        message.from_user.username,
    )
    await message.answer(
        f"Готово, AI открыт до {until:%d.%m.%Y}.",
        reply_markup=reply_markup,
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
        if parts[2] in subscription_plans():
            return subscription_plan(parts[2]), YOOKASSA_PAYMENT_METHOD_AUTO
        return subscription_plan(SUBSCRIPTION_PLAN_BASIC), parts[2]
    if len(parts) == 4:
        return subscription_plan(parts[2]), parts[3]
    return subscription_plan(SUBSCRIPTION_PLAN_BASIC), YOOKASSA_PAYMENT_METHOD_AUTO


def _yookassa_method_text(method: str) -> str:
    if method == "bank_card":
        return "картой"
    if method == "sbp":
        return "через СБП"
    return "через YooKassa"


def _yookassa_invoice_title(plan: SubscriptionPlan, method: str) -> str:
    if method == "bank_card":
        return f"AI в Kcal: {plan.title}, карта"
    if method == "sbp":
        return f"AI в Kcal: {plan.title}, СБП"
    return f"AI в Kcal: {plan.title}"


def _plan_from_callback(data: str, *, default: str) -> SubscriptionPlan:
    parts = data.split(":")
    if len(parts) >= 3 and parts[2] in subscription_plans():
        return subscription_plan(parts[2])
    return subscription_plan(default)
