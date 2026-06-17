from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import Payment, PromoCode, User

SUBSCRIPTION_PAYLOAD = "ai_subscription_30d"
YOOKASSA_PAYLOAD = "ai_subscription_30d_yookassa"
SUBSCRIPTION_PLAN_BASIC = "basic"
SUBSCRIPTION_PLAN_UNLIMITED = "unlimited"
YOOKASSA_PENDING_STATUSES = {"pending", "waiting_for_capture"}
YOOKASSA_FINAL_STATUSES = {"succeeded", "canceled", "expired", "failed"}
YOOKASSA_PAYMENT_METHOD_AUTO = "auto"
YOOKASSA_FORCED_PAYMENT_METHODS = {"bank_card", "sbp"}
YOOKASSA_PAYMENT_METHODS = YOOKASSA_FORCED_PAYMENT_METHODS | {YOOKASSA_PAYMENT_METHOD_AUTO}
YOOKASSA_TELEGRAM_PENDING_STATUS = "invoice_sent"
REFUND_WINDOW_HOURS = 24
REFUNDED_PAYMENT_STATUS = "refunded"
DUPLICATE_PAYMENT_MESSAGE = "Платёж уже был обработан, но подписка не найдена."


class SubscriptionRequiredError(RuntimeError):
    pass


def has_active_subscription(user: User) -> bool:
    return bool(user.subscription_expires_at and user.subscription_expires_at > datetime.now(UTC))


def subscription_until_text(user: User) -> str:
    if not has_active_subscription(user):
        return "AI сейчас не активен."
    return f"AI открыт до {user.subscription_expires_at:%d.%m.%Y %H:%M} UTC."


class PaymentConfigurationError(RuntimeError):
    pass


class YooKassaPaymentError(RuntimeError):
    pass


class YooKassaRefundError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubscriptionPlan:
    code: str
    title: str
    rub: int
    stars: int
    daily_limit: int | None


@dataclass(frozen=True)
class PromoDiscount:
    promo: PromoCode
    code: str
    discount_percent: int

    def apply_to_rub(self, amount_rub: int) -> int:
        return _discounted_amount(amount_rub, self.discount_percent)

    def apply_to_stars(self, amount_stars: int) -> int:
        return _discounted_amount(amount_stars, self.discount_percent)


@dataclass(frozen=True)
class PaymentRefundResult:
    payment: Payment
    status: str
    subscription_expires_at: datetime | None
    refund_id: str | None = None


def subscription_plans() -> dict[str, SubscriptionPlan]:
    return {
        SUBSCRIPTION_PLAN_BASIC: SubscriptionPlan(
            code=SUBSCRIPTION_PLAN_BASIC,
            title="Старт",
            rub=settings.ai_subscription_rub,
            stars=settings.ai_subscription_stars,
            daily_limit=settings.ai_basic_daily_request_limit,
        ),
        SUBSCRIPTION_PLAN_UNLIMITED: SubscriptionPlan(
            code=SUBSCRIPTION_PLAN_UNLIMITED,
            title="Безлимит",
            rub=settings.ai_unlimited_subscription_rub,
            stars=settings.ai_unlimited_subscription_stars,
            daily_limit=(
                None
                if settings.ai_unlimited_daily_request_limit == 0
                else settings.ai_unlimited_daily_request_limit
            ),
        ),
    }


def subscription_plan(plan_code: str | None) -> SubscriptionPlan:
    plans = subscription_plans()
    return plans.get(plan_code or SUBSCRIPTION_PLAN_BASIC, plans[SUBSCRIPTION_PLAN_BASIC])


def user_ai_daily_limit(user: User) -> int | None:
    if not has_active_subscription(user):
        return settings.ai_daily_request_limit
    return subscription_plan(user.subscription_plan).daily_limit


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_active(self, user: User) -> None:
        if not has_active_subscription(user):
            raise SubscriptionRequiredError("AI subscription is required")

    async def activate_from_stars_payment(
        self,
        user: User,
        amount_stars: int,
        payload: str,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
    ) -> datetime:
        existing = await self._payment_by_charge_id(
            telegram_payment_charge_id,
            provider_payment_charge_id,
        )
        if existing is not None:
            existing_user = await self.session.get(User, existing.user_id)
            if existing_user is None or existing_user.subscription_expires_at is None:
                raise YooKassaPaymentError(DUPLICATE_PAYMENT_MESSAGE)
            return existing_user.subscription_expires_at

        plan = subscription_plan(_plan_from_payload(payload))
        promo = await self.get_promo_for_paid_payload(_promo_from_payload(payload))
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=settings.ai_subscription_days)
        user.subscription_plan = plan.code
        if promo is not None:
            promo.promo.used_count += 1
        payment = Payment(
            user_id=user.id,
            promo_code_id=promo.promo.id if promo else None,
            amount_stars=amount_stars,
            original_amount_stars=plan.stars if promo else None,
            promo_code=promo.code if promo else None,
            promo_discount_percent=promo.discount_percent if promo else None,
            currency="XTR",
            method="stars",
            status="succeeded",
            payload=payload,
            telegram_payment_charge_id=telegram_payment_charge_id,
            provider_payment_charge_id=provider_payment_charge_id,
            paid_at=now,
        )
        self.session.add(payment)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self._payment_by_charge_id(
                telegram_payment_charge_id,
                provider_payment_charge_id,
            )
            return await self._subscription_until_for_duplicate_payment(existing)
        await self.session.refresh(user)
        return user.subscription_expires_at

    async def create_yookassa_payment(
        self,
        user: User,
        method: str,
        plan_code: str = SUBSCRIPTION_PLAN_BASIC,
        promo_code: str | None = None,
    ) -> Payment:
        plan = subscription_plan(plan_code)
        promo = await self.get_valid_promo(promo_code) if promo_code else None
        if method not in YOOKASSA_PAYMENT_METHODS:
            raise ValueError(f"Unsupported YooKassa payment method: {method}")
        if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
            raise PaymentConfigurationError("YooKassa shop id and secret key are required")

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=settings.yookassa_payment_timeout_minutes)
        amount_rub = promo.apply_to_rub(plan.rub) if promo else plan.rub
        amount_kopecks = amount_rub * 100
        payment = Payment(
            user_id=user.id,
            promo_code_id=promo.promo.id if promo else None,
            amount_kopecks=amount_kopecks,
            original_amount_kopecks=plan.rub * 100 if promo else None,
            promo_code=promo.code if promo else None,
            promo_discount_percent=promo.discount_percent if promo else None,
            currency="RUB",
            method=method,
            status="creating",
            payload=_payload_with_plan(YOOKASSA_PAYLOAD, plan.code),
            expires_at=expires_at,
        )
        self.session.add(payment)
        await self.session.flush()

        response = await _create_yookassa_payment(
            amount_rub=amount_rub,
            method=method,
            description=f"AI в Kcal: {plan.title} на {settings.ai_subscription_days} дней",
            return_url=_yookassa_return_url(),
            idempotence_key=f"kcal-payment-{payment.id}",
            metadata={
                "payment_id": str(payment.id),
                "telegram_id": str(user.telegram_id),
                "payload": _payload_with_plan(YOOKASSA_PAYLOAD, plan.code),
                "plan": plan.code,
                "promo_code": promo.code if promo else "",
            },
        )
        confirmation_url = response.get("confirmation", {}).get("confirmation_url")
        yookassa_payment_id = response.get("id")
        if not yookassa_payment_id or not confirmation_url:
            payment.status = "failed"
            payment.last_error = "ЮKassa не вернула ссылку на оплату."
            await self.session.commit()
            raise YooKassaPaymentError(payment.last_error)

        payment.status = response.get("status") or "pending"
        payment.yookassa_payment_id = yookassa_payment_id
        payment.confirmation_url = confirmation_url
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def create_yookassa_invoice_attempt(
        self,
        user: User,
        method: str,
        plan_code: str = SUBSCRIPTION_PLAN_BASIC,
        promo_code: str | None = None,
    ) -> Payment:
        plan = subscription_plan(plan_code)
        promo = await self.get_valid_promo(promo_code) if promo_code else None
        if method not in YOOKASSA_PAYMENT_METHODS:
            raise ValueError(f"Unsupported YooKassa payment method: {method}")
        if not settings.yookassa_provider_token:
            raise PaymentConfigurationError("YooKassa provider token is required")

        payment = Payment(
            user_id=user.id,
            promo_code_id=promo.promo.id if promo else None,
            amount_kopecks=(promo.apply_to_rub(plan.rub) if promo else plan.rub) * 100,
            original_amount_kopecks=plan.rub * 100 if promo else None,
            promo_code=promo.code if promo else None,
            promo_discount_percent=promo.discount_percent if promo else None,
            currency="RUB",
            method=method,
            status=YOOKASSA_TELEGRAM_PENDING_STATUS,
            payload=_payload_with_plan(YOOKASSA_PAYLOAD, plan.code),
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.yookassa_payment_timeout_minutes),
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def refresh_yookassa_payment(self, payment: Payment) -> tuple[Payment, datetime | None]:
        if payment.status in YOOKASSA_FINAL_STATUSES:
            return payment, None
        now = datetime.now(UTC)
        if payment.status == YOOKASSA_TELEGRAM_PENDING_STATUS:
            if payment.expires_at is not None and payment.expires_at <= now:
                payment.status = "expired"
                payment.last_error = "Платёж не был оплачен за отведённое время."
                await self.session.commit()
                await self.session.refresh(payment)
            return payment, None
        if not payment.yookassa_payment_id:
            payment.status = "failed"
            payment.last_error = "У платежа нет номера ЮKassa."
            await self.session.commit()
            await self.session.refresh(payment)
            return payment, None

        try:
            response = await _get_yookassa_payment(payment.yookassa_payment_id)
        except YooKassaPaymentError as exc:
            payment.last_error = str(exc)[:512]
            await self.session.commit()
            await self.session.refresh(payment)
            return payment, None

        payment.status = _normalize_yookassa_status(response)
        if payment.status == "succeeded":
            until = await self._activate_from_yookassa_payment(payment)
        else:
            until = None
            if (
                payment.status in YOOKASSA_PENDING_STATUSES
                and payment.expires_at is not None
                and payment.expires_at <= now
            ):
                payment.status = "expired"
                payment.last_error = "Платёж не был оплачен за отведённое время."
            if payment.status in {"canceled", "failed"}:
                payment.last_error = _extract_cancellation_reason(response)
            await self.session.commit()
        await self.session.refresh(payment)
        return payment, until

    async def get_payment_for_user(self, payment_id: int, user: User) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id, Payment.user_id == user.id)
        )
        return result.scalar_one_or_none()

    async def activate_from_yookassa_invoice_payment(
        self,
        payment: Payment,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str | None,
    ) -> datetime:
        locked_payment = await self._payment_for_update(payment.id)
        if locked_payment is None:
            raise YooKassaPaymentError("Платёж не найден.")
        payment = locked_payment

        existing = await self._payment_by_charge_id(
            telegram_payment_charge_id,
            provider_payment_charge_id,
        )
        if existing is not None and existing.id != payment.id:
            existing_user = await self.session.get(User, existing.user_id)
            if existing_user is None or existing_user.subscription_expires_at is None:
                raise YooKassaPaymentError(DUPLICATE_PAYMENT_MESSAGE)
            return existing_user.subscription_expires_at
        if payment.paid_at is not None:
            result = await self.session.execute(select(User).where(User.id == payment.user_id))
            user = result.scalar_one()
            return user.subscription_expires_at

        result = await self.session.execute(select(User).where(User.id == payment.user_id))
        user = result.scalar_one()
        plan = subscription_plan(_plan_from_payload(payment.payload))
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=settings.ai_subscription_days)
        user.subscription_plan = plan.code
        if payment.promo_code_id is not None:
            promo = await self.session.get(PromoCode, payment.promo_code_id)
            if promo is not None:
                promo.used_count += 1
        payment.status = "succeeded"
        payment.telegram_payment_charge_id = telegram_payment_charge_id
        payment.provider_payment_charge_id = provider_payment_charge_id
        payment.paid_at = now
        payment.last_error = None
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self._payment_by_charge_id(
                telegram_payment_charge_id,
                provider_payment_charge_id,
            )
            return await self._subscription_until_for_duplicate_payment(existing)
        await self.session.refresh(user)
        return user.subscription_expires_at

    async def pending_yookassa_payments(self, limit: int = 50) -> list[Payment]:
        result = await self.session.execute(
            select(Payment)
            .where(Payment.method.in_(YOOKASSA_PAYMENT_METHODS))
            .where(
                Payment.status.in_(
                    YOOKASSA_PENDING_STATUSES
                    | {"creating", YOOKASSA_TELEGRAM_PENDING_STATUS}
                )
            )
            .order_by(Payment.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def latest_refundable_payment(self, user: User) -> Payment | None:
        cutoff = datetime.now(UTC) - timedelta(hours=REFUND_WINDOW_HOURS)
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .where(Payment.status == "succeeded")
            .where(Payment.paid_at.is_not(None))
            .where(Payment.paid_at >= cutoff)
            .order_by(Payment.paid_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def refund_yookassa_payment(self, payment: Payment) -> PaymentRefundResult:
        if payment.currency != "RUB" or payment.method not in YOOKASSA_PAYMENT_METHODS:
            raise YooKassaRefundError("Это не платёж YooKassa.")
        if payment.amount_kopecks is None:
            raise YooKassaRefundError("Не нашёл сумму платежа.")
        if not _payment_is_inside_refund_window(payment):
            raise YooKassaRefundError("24 часа на автоматический возврат уже прошли.")
        if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
            raise PaymentConfigurationError("YooKassa shop id and secret key are required")

        yookassa_payment_id = payment.yookassa_payment_id or payment.provider_payment_charge_id
        if not yookassa_payment_id:
            raise YooKassaRefundError("Не нашёл номер платежа YooKassa для возврата.")

        response = await _create_yookassa_refund(
            payment_id=yookassa_payment_id,
            amount_kopecks=payment.amount_kopecks,
            idempotence_key=f"kcal-refund-{payment.id}",
            metadata={"payment_id": str(payment.id), "telegram_user_id": str(payment.user_id)},
        )
        status = str(response.get("status") or "pending")
        refund_id = str(response.get("id") or "") or None

        if status == "succeeded":
            result = await self.mark_payment_refunded(payment, refund_id=refund_id)
            user = await self.session.get(User, result.user_id)
            return PaymentRefundResult(
                payment=result,
                status=status,
                subscription_expires_at=user.subscription_expires_at if user else None,
                refund_id=refund_id,
            )
        if status == "canceled":
            payment.last_error = (
                _extract_cancellation_reason(response) or "Возврат отменён YooKassa."
            )
            await self.session.commit()
            await self.session.refresh(payment)
            raise YooKassaRefundError(payment.last_error)

        payment.status = "refund_pending"
        payment.last_error = f"refund_id={refund_id}"[:512] if refund_id else "Возврат в обработке."
        await self.session.commit()
        await self.session.refresh(payment)
        result = await self.session.get(User, payment.user_id)
        return PaymentRefundResult(
            payment=payment,
            status=status,
            subscription_expires_at=result.subscription_expires_at if result else None,
            refund_id=refund_id,
        )

    async def mark_payment_refunded(
        self,
        payment: Payment,
        *,
        refund_id: str | None = None,
    ) -> Payment:
        result = await self.session.execute(select(User).where(User.id == payment.user_id))
        user = result.scalar_one()
        now = datetime.now(UTC)
        if user.subscription_expires_at is not None:
            reduced_until = user.subscription_expires_at - timedelta(
                days=settings.ai_subscription_days
            )
            user.subscription_expires_at = reduced_until if reduced_until > now else now
        payment.status = REFUNDED_PAYMENT_STATUS
        payment.last_error = f"refund_id={refund_id}"[:512] if refund_id else None
        await self.session.commit()
        await self.session.refresh(payment)
        await self.session.refresh(user)
        return payment

    async def _activate_from_yookassa_payment(self, payment: Payment) -> datetime:
        locked_payment = await self._payment_for_update(payment.id)
        if locked_payment is None:
            raise YooKassaPaymentError("Платёж не найден.")
        payment = locked_payment

        if payment.paid_at is not None:
            result = await self.session.execute(select(User).where(User.id == payment.user_id))
            user = result.scalar_one()
            return user.subscription_expires_at

        result = await self.session.execute(select(User).where(User.id == payment.user_id))
        user = result.scalar_one()
        plan = subscription_plan(_plan_from_payload(payment.payload))
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=settings.ai_subscription_days)
        user.subscription_plan = plan.code
        if payment.promo_code_id is not None:
            promo = await self.session.get(PromoCode, payment.promo_code_id)
            if promo is not None:
                promo.used_count += 1
        payment.status = "succeeded"
        payment.paid_at = now
        payment.last_error = None
        await self.session.commit()
        await self.session.refresh(user)
        return user.subscription_expires_at

    async def _payment_for_update(self, payment_id: int) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.id == payment_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def _subscription_until_for_duplicate_payment(self, payment: Payment | None) -> datetime:
        if payment is None:
            raise YooKassaPaymentError(DUPLICATE_PAYMENT_MESSAGE)
        existing_user = await self.session.get(User, payment.user_id)
        if existing_user is None or existing_user.subscription_expires_at is None:
            raise YooKassaPaymentError(DUPLICATE_PAYMENT_MESSAGE)
        return existing_user.subscription_expires_at

    async def _payment_by_charge_id(
        self,
        telegram_payment_charge_id: str | None,
        provider_payment_charge_id: str | None,
    ) -> Payment | None:
        charge_ids = [
            (Payment.telegram_payment_charge_id, telegram_payment_charge_id),
            (Payment.provider_payment_charge_id, provider_payment_charge_id),
        ]
        for column, value in charge_ids:
            if not value:
                continue
            result = await self.session.execute(select(Payment).where(column == value).limit(1))
            payment = result.scalar_one_or_none()
            if payment is not None:
                return payment
        return None

    async def get_valid_promo(self, code: str | None) -> PromoDiscount | None:
        promo = await self._promo_by_code(code)
        if promo is None or not promo_is_available(promo):
            return None
        return PromoDiscount(
            promo=promo,
            code=promo.code,
            discount_percent=promo.discount_percent,
        )

    async def get_promo_for_paid_payload(self, code: str | None) -> PromoDiscount | None:
        promo = await self._promo_by_code(code)
        if promo is None:
            return None
        return PromoDiscount(
            promo=promo,
            code=promo.code,
            discount_percent=promo.discount_percent,
        )

    async def _promo_by_code(self, code: str | None) -> PromoCode | None:
        normalized = normalize_promo_code(code)
        if not normalized:
            return None
        result = await self.session.execute(
            select(PromoCode).where(PromoCode.code == normalized).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_promo(
        self,
        *,
        code: str,
        discount_percent: int,
        max_uses: int | None = None,
        expires_at: datetime | None = None,
        note: str | None = None,
    ) -> PromoCode:
        normalized = normalize_promo_code(code)
        if not normalized:
            raise ValueError("Promo code is empty")
        if discount_percent <= 0 or discount_percent > 95:
            raise ValueError("Discount percent must be between 1 and 95")
        promo = PromoCode(
            code=normalized,
            discount_percent=discount_percent,
            max_uses=max_uses,
            expires_at=expires_at,
            note=note[:255] if note else None,
            active=True,
            used_count=0,
        )
        self.session.add(promo)
        await self.session.commit()
        await self.session.refresh(promo)
        return promo

    async def active_promos(self, limit: int = 20) -> list[PromoCode]:
        result = await self.session.execute(
            select(PromoCode).order_by(PromoCode.created_at.desc()).limit(limit)
        )
        return list(result.scalars())

    async def disable_promo(self, promo_id: int) -> PromoCode | None:
        promo = await self.session.get(PromoCode, promo_id)
        if promo is None:
            return None
        promo.active = False
        await self.session.commit()
        await self.session.refresh(promo)
        return promo


def _yookassa_return_url() -> str:
    if settings.yookassa_return_url:
        return settings.yookassa_return_url
    return f"{settings.public_api_url.rstrip('/')}/payments/yookassa/return"


def _payload_with_plan(payload: str, plan_code: str) -> str:
    return f"{payload}:{subscription_plan(plan_code).code}"


def _plan_from_payload(payload: str) -> str:
    parts = payload.split(":")
    if len(parts) >= 2 and parts[1] in subscription_plans():
        return parts[1]
    return SUBSCRIPTION_PLAN_BASIC


def _promo_from_payload(payload: str) -> str | None:
    parts = payload.split(":")
    if len(parts) >= 3:
        return normalize_promo_code(parts[2])
    return None


def payload_with_promo(payload: str, plan_code: str, promo_code: str | None = None) -> str:
    base = _payload_with_plan(payload, plan_code)
    promo = normalize_promo_code(promo_code)
    return f"{base}:{promo}" if promo else base


def normalize_promo_code(code: str | None) -> str:
    return "".join((code or "").strip().upper().split())[:64]


def promo_is_available(promo: PromoCode, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if not promo.active:
        return False
    if promo.expires_at is not None and promo.expires_at <= now:
        return False
    return not (promo.max_uses is not None and promo.used_count >= promo.max_uses)


def _discounted_amount(amount: int, discount_percent: int) -> int:
    discounted = round(amount * (100 - discount_percent) / 100)
    return max(discounted, 1)


def _payment_is_inside_refund_window(payment: Payment) -> bool:
    if payment.paid_at is None:
        return False
    return payment.paid_at >= datetime.now(UTC) - timedelta(hours=REFUND_WINDOW_HOURS)


async def _create_yookassa_payment(
    *,
    amount_rub: int,
    method: str,
    description: str,
    return_url: str,
    idempotence_key: str,
    metadata: dict[str, str],
) -> dict[str, Any]:
    body = {
        "amount": {
            "value": f"{Decimal(amount_rub):.2f}",
            "currency": "RUB",
        },
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }
    if method in YOOKASSA_FORCED_PAYMENT_METHODS:
        body["payment_method_data"] = {"type": method}
    return await _yookassa_request(
        "POST",
        "/payments",
        idempotence_key=idempotence_key,
        json=body,
    )


async def _get_yookassa_payment(payment_id: str) -> dict[str, Any]:
    return await _yookassa_request("GET", f"/payments/{payment_id}")


async def _create_yookassa_refund(
    *,
    payment_id: str,
    amount_kopecks: int,
    idempotence_key: str,
    metadata: dict[str, str],
) -> dict[str, Any]:
    amount_rub = Decimal(amount_kopecks) / Decimal(100)
    body = {
        "amount": {
            "value": f"{amount_rub:.2f}",
            "currency": "RUB",
        },
        "payment_id": payment_id,
        "metadata": metadata,
    }
    return await _yookassa_request(
        "POST",
        "/refunds",
        idempotence_key=idempotence_key,
        json=body,
    )


async def _yookassa_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    headers = kwargs.pop("headers", {})
    if method == "POST":
        headers["Idempotence-Key"] = kwargs.pop("idempotence_key", str(uuid.uuid4()))
    try:
        async with httpx.AsyncClient(
            base_url="https://api.yookassa.ru/v3",
            auth=(settings.yookassa_shop_id, settings.yookassa_secret_key),
            timeout=20,
        ) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        raise YooKassaPaymentError("ЮKassa временно недоступна.") from exc

    if response.status_code >= 400:
        raise YooKassaPaymentError(_error_message(response))
    data = response.json()
    if not isinstance(data, dict):
        raise YooKassaPaymentError("ЮKassa вернула неожиданный ответ.")
    return data


def _normalize_yookassa_status(response: dict[str, Any]) -> str:
    status = str(response.get("status") or "failed")
    if status == "succeeded" and response.get("paid") is False:
        return "failed"
    return status


def _extract_cancellation_reason(response: dict[str, Any]) -> str | None:
    cancellation = response.get("cancellation_details")
    if not isinstance(cancellation, dict):
        return None
    reason = cancellation.get("reason")
    party = cancellation.get("party")
    if reason and party:
        return f"{party}: {reason}"[:512]
    if reason:
        return str(reason)[:512]
    return None


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return "ЮKassa отклонила запрос."
    if not isinstance(data, dict):
        return "ЮKassa отклонила запрос."
    description = data.get("description") or data.get("message")
    return str(description or "ЮKassa отклонила запрос.")[:512]
