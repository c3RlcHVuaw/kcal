from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import ActivityLog, AIUsage, FoodEntry, User, WaterLog, WeightLog
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
        attached = await self.users.attach_referrer(user, code)
        if attached and settings.premium_trial_days:
            await self.grant_premium_trial(user, require_inactive=False)
        return attached

    async def reward_referrer_for_first_payment(self, user: User) -> User | None:
        if user.referred_by_user_id is None or user.referral_rewarded_at is not None:
            return None
        if user.active_referral_rewarded_at is not None:
            return None

        referrer = await self.session.get(User, user.referred_by_user_id)
        if referrer is None:
            return None
        if referrer.first_active_referral_rewarded_at is None:
            return None

        now = datetime.now(UTC)
        _extend_subscription(referrer, settings.referral_reward_days, now=now)
        user.referral_rewarded_at = now
        await self.session.commit()
        await self.session.refresh(referrer)
        await self.session.refresh(user)
        return referrer

    async def reward_referrer_for_activity(self, user: User) -> User | None:
        if user.referred_by_user_id is None:
            return None
        if user.active_referral_rewarded_at is not None:
            return None
        if not user.referred_at or datetime.now(UTC) > _active_window_end(user):
            return None

        active_days = await self.referral_active_days(user)
        if active_days < settings.referral_active_required_days:
            return None

        referrer = await self.session.get(User, user.referred_by_user_id)
        if referrer is None or referrer.first_active_referral_rewarded_at is not None:
            return None

        now = datetime.now(UTC)
        _extend_subscription(referrer, settings.referral_reward_days, now=now)
        referrer.first_active_referral_rewarded_at = now
        user.active_referral_rewarded_at = now
        await self.session.commit()
        await self.session.refresh(referrer)
        await self.session.refresh(user)
        return referrer

    async def referral_active_days(self, user: User) -> int:
        if not user.referred_at:
            return 0

        tz = ZoneInfo(user.timezone)
        start_date = user.referred_at.astimezone(tz).date()
        end_date = start_date + timedelta(days=settings.referral_active_window_days - 1)
        start_at = datetime.combine(start_date, time.min, tzinfo=tz)
        end_at = datetime.combine(end_date, time.max, tzinfo=tz)
        active_dates: set = set()

        for model in (FoodEntry, WaterLog, WeightLog, ActivityLog):
            result = await self.session.execute(
                select(model.created_at).where(
                    model.user_id == user.id,
                    model.created_at >= start_at,
                    model.created_at <= end_at,
                )
            )
            active_dates.update(_as_user_date(created_at, tz) for created_at in result.scalars())

        result = await self.session.execute(
            select(AIUsage.usage_date).where(
                AIUsage.user_id == user.id,
                AIUsage.usage_date >= start_date,
                AIUsage.usage_date <= end_date,
                AIUsage.request_count > 0,
            )
        )
        active_dates.update(result.scalars())
        return len(active_dates)

    async def grant_premium_trial(
        self,
        user: User,
        *,
        require_inactive: bool = True,
    ) -> datetime | None:
        if user.premium_trial_used_at is not None:
            return None
        if require_inactive and has_active_subscription(user):
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


def _active_window_end(user: User) -> datetime:
    assert user.referred_at is not None
    return user.referred_at + timedelta(days=settings.referral_active_window_days)


def _as_user_date(value: datetime, tz: ZoneInfo):
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz).date()
