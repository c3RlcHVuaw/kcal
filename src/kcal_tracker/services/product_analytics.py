from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import FoodEntry, LandingEvent, Payment, QualityEvent, User

AI_ACCEPT_EVENTS = {
    "webapp_ai_accept",
    "webapp_ai_saved_unedited",
    "webapp_ai_saved",
    "food_ai_accept",
    "food_ai_saved",
}
AI_EDIT_EVENTS = {
    "webapp_ai_adjust",
    "webapp_ai_saved_edited",
    "webapp_ai_edit",
    "webapp_ai_edited",
    "food_ai_edit",
    "food_ai_edited",
}
AI_REJECT_EVENTS = {
    "webapp_ai_reject",
    "food_not_it",
}
AI_FAILURE_EVENTS = {
    "webapp_ai_failed",
    "food_ai_failed",
    "webapp_search_failed",
    "food_no_match",
}


@dataclass(frozen=True)
class AIQualityMetrics:
    accepted: int
    edited: int
    rejected: int
    failed: int

    @property
    def reviewed(self) -> int:
        return self.accepted + self.edited + self.rejected

    @property
    def total_signals(self) -> int:
        return self.reviewed + self.failed

    @property
    def acceptance_rate(self) -> float | None:
        if self.reviewed == 0:
            return None
        return self.accepted / self.reviewed

    @property
    def edit_rate(self) -> float | None:
        if self.reviewed == 0:
            return None
        return self.edited / self.reviewed

    @property
    def failure_rate(self) -> float | None:
        if self.total_signals == 0:
            return None
        return self.failed / self.total_signals


@dataclass(frozen=True)
class FunnelMetrics:
    landing_views: int
    bot_clicks: int
    new_users: int
    onboarded_users: int
    paywall_opens: int
    payment_starts: int
    successful_payments: int

    @property
    def landing_to_bot_rate(self) -> float | None:
        return _ratio(self.bot_clicks, self.landing_views)

    @property
    def onboarding_rate(self) -> float | None:
        return _ratio(self.onboarded_users, self.new_users)

    @property
    def paywall_to_payment_start_rate(self) -> float | None:
        return _ratio(self.payment_starts, self.paywall_opens)

    @property
    def payment_success_rate(self) -> float | None:
        return _ratio(self.successful_payments, self.payment_starts)


@dataclass(frozen=True)
class RetentionMetrics:
    cohort_users: int
    d1_users: int
    d7_users: int

    @property
    def d1_rate(self) -> float | None:
        return _ratio(self.d1_users, self.cohort_users)

    @property
    def d7_rate(self) -> float | None:
        return _ratio(self.d7_users, self.cohort_users)


class ProductAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ai_quality(self, start: datetime, end: datetime) -> AIQualityMetrics:
        rows = await self.session.execute(
            select(QualityEvent.event_type, func.count(QualityEvent.id))
            .where(QualityEvent.created_at >= start, QualityEvent.created_at <= end)
            .group_by(QualityEvent.event_type)
        )
        counts = {event_type: count for event_type, count in rows.all()}
        return AIQualityMetrics(
            accepted=_sum_events(counts, AI_ACCEPT_EVENTS),
            edited=_sum_events(counts, AI_EDIT_EVENTS),
            rejected=_sum_events(counts, AI_REJECT_EVENTS),
            failed=_sum_events(counts, AI_FAILURE_EVENTS),
        )

    async def funnel(self, start: datetime, end: datetime) -> FunnelMetrics:
        landing_views = await self._count_landing_events(start, end, "view")
        bot_clicks = await self._count_landing_events(start, end, "bot_click")
        paywall_opens = await self._count_quality_events(start, end, "webapp_paywall_open")
        payment_starts = await self._count_quality_events(start, end, "webapp_payment_start")

        new_users = await self.session.scalar(
            select(func.count(User.id)).where(User.created_at >= start, User.created_at <= end)
        )
        onboarded_users = await self.session.scalar(
            select(func.count(User.id)).where(
                User.created_at >= start,
                User.created_at <= end,
                User.onboarding_completed.is_(True),
            )
        )
        successful_payments = await self.session.scalar(
            select(func.count(Payment.id)).where(
                Payment.created_at >= start,
                Payment.created_at <= end,
                Payment.status == "succeeded",
            )
        )

        return FunnelMetrics(
            landing_views=landing_views,
            bot_clicks=bot_clicks,
            new_users=int(new_users or 0),
            onboarded_users=int(onboarded_users or 0),
            paywall_opens=paywall_opens,
            payment_starts=payment_starts,
            successful_payments=int(successful_payments or 0),
        )

    async def retention(self, start: datetime, end: datetime) -> RetentionMetrics:
        user_rows = await self.session.execute(
            select(User.id, User.created_at).where(User.created_at >= start, User.created_at <= end)
        )
        users = {user_id: created_at for user_id, created_at in user_rows.all()}
        if not users:
            return RetentionMetrics(cohort_users=0, d1_users=0, d7_users=0)

        max_window_end = max(created_at for created_at in users.values()) + timedelta(days=8)
        entry_rows = await self.session.execute(
            select(FoodEntry.user_id, FoodEntry.created_at).where(
                FoodEntry.user_id.in_(list(users)),
                FoodEntry.created_at >= start,
                FoodEntry.created_at < max_window_end,
            )
        )

        d1_users: set[int] = set()
        d7_users: set[int] = set()
        for user_id, entry_created_at in entry_rows.all():
            created_at = users[user_id]
            if _in_day_window(entry_created_at, created_at, day_offset=1):
                d1_users.add(user_id)
            if _in_day_window(entry_created_at, created_at, day_offset=7):
                d7_users.add(user_id)

        return RetentionMetrics(
            cohort_users=len(users),
            d1_users=len(d1_users),
            d7_users=len(d7_users),
        )

    async def _count_landing_events(self, start: datetime, end: datetime, event_type: str) -> int:
        count = await self.session.scalar(
            select(func.count(LandingEvent.id)).where(
                LandingEvent.created_at >= start,
                LandingEvent.created_at <= end,
                LandingEvent.event_type == event_type,
            )
        )
        return int(count or 0)

    async def _count_quality_events(self, start: datetime, end: datetime, event_type: str) -> int:
        count = await self.session.scalar(
            select(func.count(QualityEvent.id)).where(
                QualityEvent.created_at >= start,
                QualityEvent.created_at <= end,
                QualityEvent.event_type == event_type,
            )
        )
        return int(count or 0)


def _sum_events(counts: dict[str, int], event_types: set[str]) -> int:
    return sum(counts.get(event_type, 0) for event_type in event_types)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _in_day_window(value: datetime, start: datetime, *, day_offset: int) -> bool:
    window_start = start + timedelta(days=day_offset)
    window_end = window_start + timedelta(days=1)
    return window_start <= value < window_end
