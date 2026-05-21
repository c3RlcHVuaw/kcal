from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import Payment, User

SUBSCRIPTION_PAYLOAD = "ai_subscription_30d"
YOOKASSA_PAYLOAD = "ai_subscription_30d_yookassa"
YOOKASSA_PENDING_STATUSES = {"pending", "waiting_for_capture"}
YOOKASSA_FINAL_STATUSES = {"succeeded", "canceled", "expired", "failed"}
YOOKASSA_PAYMENT_METHODS = {"bank_card", "sbp"}
YOOKASSA_TELEGRAM_PENDING_STATUS = "invoice_sent"


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
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=settings.ai_subscription_days)
        self.session.add(
            Payment(
                user_id=user.id,
                amount_stars=amount_stars,
                currency="XTR",
                method="stars",
                status="succeeded",
                payload=payload,
                telegram_payment_charge_id=telegram_payment_charge_id,
                provider_payment_charge_id=provider_payment_charge_id,
                paid_at=now,
            )
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user.subscription_expires_at

    async def create_yookassa_payment(
        self,
        user: User,
        method: str,
    ) -> Payment:
        if method not in YOOKASSA_PAYMENT_METHODS:
            raise ValueError(f"Unsupported YooKassa payment method: {method}")
        if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
            raise PaymentConfigurationError("YooKassa shop id and secret key are required")

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=settings.yookassa_payment_timeout_minutes)
        amount_kopecks = settings.ai_subscription_rub * 100
        payment = Payment(
            user_id=user.id,
            amount_kopecks=amount_kopecks,
            currency="RUB",
            method=method,
            status="creating",
            payload=YOOKASSA_PAYLOAD,
            expires_at=expires_at,
        )
        self.session.add(payment)
        await self.session.flush()

        response = await _create_yookassa_payment(
            amount_rub=settings.ai_subscription_rub,
            method=method,
            description=f"AI в Kcal на {settings.ai_subscription_days} дней",
            return_url=_yookassa_return_url(),
            metadata={
                "payment_id": str(payment.id),
                "telegram_id": str(user.telegram_id),
                "payload": YOOKASSA_PAYLOAD,
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

    async def create_yookassa_invoice_attempt(self, user: User, method: str) -> Payment:
        if method not in YOOKASSA_PAYMENT_METHODS:
            raise ValueError(f"Unsupported YooKassa payment method: {method}")
        if not settings.yookassa_provider_token:
            raise PaymentConfigurationError("YooKassa provider token is required")

        payment = Payment(
            user_id=user.id,
            amount_kopecks=settings.ai_subscription_rub * 100,
            currency="RUB",
            method=method,
            status=YOOKASSA_TELEGRAM_PENDING_STATUS,
            payload=YOOKASSA_PAYLOAD,
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
        if payment.paid_at is not None:
            result = await self.session.execute(select(User).where(User.id == payment.user_id))
            user = result.scalar_one()
            return user.subscription_expires_at

        result = await self.session.execute(select(User).where(User.id == payment.user_id))
        user = result.scalar_one()
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=settings.ai_subscription_days)
        payment.status = "succeeded"
        payment.telegram_payment_charge_id = telegram_payment_charge_id
        payment.provider_payment_charge_id = provider_payment_charge_id
        payment.paid_at = now
        payment.last_error = None
        await self.session.commit()
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

    async def _activate_from_yookassa_payment(self, payment: Payment) -> datetime:
        if payment.paid_at is not None:
            result = await self.session.execute(select(User).where(User.id == payment.user_id))
            user = result.scalar_one()
            return user.subscription_expires_at

        result = await self.session.execute(select(User).where(User.id == payment.user_id))
        user = result.scalar_one()
        now = datetime.now(UTC)
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=settings.ai_subscription_days)
        payment.paid_at = now
        payment.last_error = None
        await self.session.commit()
        await self.session.refresh(user)
        return user.subscription_expires_at


def _yookassa_return_url() -> str:
    if settings.yookassa_return_url:
        return settings.yookassa_return_url
    return f"{settings.public_api_url.rstrip('/')}/payments/yookassa/return"


async def _create_yookassa_payment(
    *,
    amount_rub: int,
    method: str,
    description: str,
    return_url: str,
    metadata: dict[str, str],
) -> dict[str, Any]:
    body = {
        "amount": {
            "value": f"{Decimal(amount_rub):.2f}",
            "currency": "RUB",
        },
        "payment_method_data": {"type": method},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }
    return await _yookassa_request("POST", "/payments", json=body)


async def _get_yookassa_payment(payment_id: str) -> dict[str, Any]:
    return await _yookassa_request("GET", f"/payments/{payment_id}")


async def _yookassa_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    headers = kwargs.pop("headers", {})
    if method == "POST":
        headers["Idempotence-Key"] = str(uuid.uuid4())
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
