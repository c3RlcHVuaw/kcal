from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import ActivityLog, AIUsage, FoodEntry, User, WaterLog, WeightLog
from kcal_tracker.services.subscriptions import has_active_subscription
from kcal_tracker.services.users import UserService


@dataclass(frozen=True)
class ReferralFriendProgress:
    active_days: int
    required_days: int
    paid: bool
    active_rewarded: bool
    payment_rewarded: bool


@dataclass(frozen=True)
class ReferralDashboard:
    link: str
    invited_count: int
    first_active_reward_used: bool
    friends: list[ReferralFriendProgress]


@dataclass(frozen=True)
class WeeklyMission:
    key: str
    title: str
    current: int
    target: int

    @property
    def completed(self) -> bool:
        return self.current >= self.target


@dataclass(frozen=True)
class WeeklyMissions:
    week_start: date
    missions: list[WeeklyMission]
    bonus_claimed: bool

    @property
    def completed_count(self) -> int:
        return sum(1 for mission in self.missions if mission.completed)

    @property
    def eligible_for_bonus(self) -> bool:
        return self.completed_count >= 2 and not self.bonus_claimed


class GrowthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserService(session)

    async def referral_link(self, user: User, bot_username: str) -> str:
        code = await self.users.ensure_referral_code(user)
        return f"https://t.me/{bot_username}?start=ref_{code}"

    async def referral_dashboard(self, user: User, bot_username: str) -> ReferralDashboard:
        link = await self.referral_link(user, bot_username)
        result = await self.session.execute(
            select(User)
            .where(User.referred_by_user_id == user.id)
            .order_by(User.created_at.asc())
        )
        invited = list(result.scalars())
        friends = []
        for friend in invited[:10]:
            friends.append(
                ReferralFriendProgress(
                    active_days=await self.referral_active_days(friend),
                    required_days=settings.referral_active_required_days,
                    paid=friend.referral_rewarded_at is not None
                    or friend.subscription_expires_at is not None,
                    active_rewarded=friend.active_referral_rewarded_at is not None,
                    payment_rewarded=friend.referral_rewarded_at is not None,
                )
            )
        return ReferralDashboard(
            link=link,
            invited_count=len(invited),
            first_active_reward_used=user.first_active_referral_rewarded_at is not None,
            friends=friends,
        )

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

    async def weekly_missions(self, user: User) -> WeeklyMissions:
        tz = ZoneInfo(user.timezone)
        today = datetime.now(tz).date()
        week_start = today - timedelta(days=today.weekday())
        start_at = datetime.combine(week_start, time.min, tzinfo=tz)
        end_at = datetime.combine(week_start + timedelta(days=6), time.max, tzinfo=tz)
        food_dates = await self._activity_dates(FoodEntry, user, start_at, end_at, tz)
        water_dates = await self._activity_dates(WaterLog, user, start_at, end_at, tz)
        weight_dates = await self._activity_dates(WeightLog, user, start_at, end_at, tz)
        activity_dates = await self._activity_dates(ActivityLog, user, start_at, end_at, tz)

        missions = [
            WeeklyMission("food", "Еда 5 дней", len(food_dates), 5),
            WeeklyMission("water", "Вода 5 дней", len(water_dates), 5),
            WeeklyMission("weight", "Вес 2 дня", len(weight_dates), 2),
            WeeklyMission("activity", "Активность 2 дня", len(activity_dates), 2),
        ]
        return WeeklyMissions(
            week_start=week_start,
            missions=missions,
            bonus_claimed=user.weekly_mission_bonus_week == week_start,
        )

    async def claim_weekly_mission_bonus(self, user: User) -> datetime | None:
        missions = await self.weekly_missions(user)
        if not missions.eligible_for_bonus:
            return None

        now = datetime.now(UTC)
        user.weekly_mission_bonus_week = missions.week_start
        _extend_subscription(user, settings.premium_trial_days, now=now)
        await self.session.commit()
        await self.session.refresh(user)
        return user.subscription_expires_at

    async def _activity_dates(self, model, user: User, start_at: datetime, end_at: datetime, tz):
        result = await self.session.execute(
            select(model.created_at).where(
                model.user_id == user.id,
                model.created_at >= start_at,
                model.created_at <= end_at,
            )
        )
        return {_as_user_date(created_at, tz) for created_at in result.scalars()}


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
