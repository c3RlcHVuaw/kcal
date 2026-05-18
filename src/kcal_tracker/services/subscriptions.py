from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import Payment, User

SUBSCRIPTION_PAYLOAD = "ai_subscription_30d"


class SubscriptionRequiredError(RuntimeError):
    pass


def has_active_subscription(user: User) -> bool:
    return bool(user.subscription_expires_at and user.subscription_expires_at > datetime.now(UTC))


def subscription_until_text(user: User) -> str:
    if not has_active_subscription(user):
        return "AI сейчас не активен."
    return f"AI открыт до {user.subscription_expires_at:%d.%m.%Y %H:%M} UTC."


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
                payload=payload,
                telegram_payment_charge_id=telegram_payment_charge_id,
                provider_payment_charge_id=provider_payment_charge_id,
            )
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user.subscription_expires_at
