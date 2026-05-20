from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import User
from kcal_tracker.services.subscriptions import has_active_subscription
from kcal_tracker.services.users import UserService


class GrowthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserService(session)

    async def referral_link(self, user: User, bot_username: str) -> str:
        code = await self.users.ensure_referral_code(user)
        return f"https://t.me/{bot_username}?start=ref_{code}"

    async def apply_referral_start(self, user: User, start_payload: str | None) -> bool:
        code = _referral_code_from_payload(start_payload)
        return await self.users.attach_referrer(user, code)

    async def reward_referrer_for_first_payment(self, user: User) -> User | None:
        if user.referred_by_user_id is None or user.referral_rewarded_at is not None:
            return None

        referrer = await self.session.get(User, user.referred_by_user_id)
        if referrer is None:
            return None

        now = datetime.now(UTC)
        _extend_subscription(referrer, settings.referral_reward_days, now=now)
        user.referral_rewarded_at = now
        await self.session.commit()
        await self.session.refresh(referrer)
        await self.session.refresh(user)
        return referrer

    async def grant_premium_trial(self, user: User) -> datetime | None:
        if user.premium_trial_used_at is not None or has_active_subscription(user):
            return None

        now = datetime.now(UTC)
        user.premium_trial_used_at = now
        _extend_subscription(user, settings.premium_trial_days, now=now)
        await self.session.commit()
        await self.session.refresh(user)
        return user.subscription_expires_at

    async def grant_winback_offer(self, user: User) -> datetime | None:
        if user.winback_used_at is not None or has_active_subscription(user):
            return None
        if user.subscription_expires_at is None:
            return None

        now = datetime.now(UTC)
        user.winback_used_at = now
        _extend_subscription(user, settings.winback_offer_days, now=now)
        await self.session.commit()
        await self.session.refresh(user)
        return user.subscription_expires_at


def progress_share_url(text: str) -> str:
    return f"https://t.me/share/url?text={quote(text)}"


def _extend_subscription(user: User, days: int, *, now: datetime) -> None:
    base = user.subscription_expires_at if has_active_subscription(user) else now
    user.subscription_expires_at = base + timedelta(days=days)


def _referral_code_from_payload(payload: str | None) -> str | None:
    if not payload or not payload.startswith("ref_"):
        return None
    code = payload.removeprefix("ref_").strip()
    return code or None
