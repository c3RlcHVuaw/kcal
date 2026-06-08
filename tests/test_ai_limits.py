from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from kcal_tracker.api.routes import (
    _ai_usage_summary,
    _ensure_webapp_ai_allowed,
    _remaining_ai_for_webapp,
)
from kcal_tracker.models import User


class FakeUsageService:
    def __init__(
        self,
        *,
        used_today: int = 0,
        lifetime_used: int = 0,
        remaining_today: int = 30,
        remaining_trial: int = 3,
    ) -> None:
        self.used_today = used_today
        self.lifetime_used = lifetime_used
        self.remaining_today_value = remaining_today
        self.remaining_trial_value = remaining_trial
        self.paid_checked = False
        self.trial_checked = False

    async def today_count(self, user: User) -> int:
        return self.used_today

    async def lifetime_count(self, user: User) -> int:
        return self.lifetime_used

    async def remaining_today(self, user: User) -> int:
        return self.remaining_today_value

    async def remaining_trial(self, user: User) -> int:
        return self.remaining_trial_value

    async def ensure_allowed(self, user: User, request_count: int = 1) -> None:
        self.paid_checked = True

    async def ensure_trial_allowed(self, user: User, request_count: int = 1) -> None:
        self.trial_checked = True


def test_webapp_free_ai_summary_uses_trial_remaining() -> None:
    user = User(id=1, telegram_id=1001)
    usage = FakeUsageService(used_today=1, lifetime_used=2, remaining_today=29, remaining_trial=1)

    summary = asyncio.run(_ai_usage_summary(user, usage))

    assert summary.is_trial is True
    assert summary.trial_used == 2
    assert summary.trial_limit == 3
    assert summary.trial_remaining == 1
    assert summary.remaining_today == 1


def test_webapp_free_ai_check_uses_trial_limit() -> None:
    user = User(id=1, telegram_id=1001)
    usage = FakeUsageService(remaining_today=29, remaining_trial=1)

    asyncio.run(_ensure_webapp_ai_allowed(user, usage))

    assert usage.trial_checked is True
    assert usage.paid_checked is False
    assert asyncio.run(_remaining_ai_for_webapp(user, usage)) == 1


def test_webapp_paid_ai_check_uses_plan_daily_limit() -> None:
    user = User(
        id=1,
        telegram_id=1001,
        subscription_expires_at=datetime.now(UTC) + timedelta(days=1),
        subscription_plan="basic",
    )
    usage = FakeUsageService(remaining_today=12, remaining_trial=0)

    asyncio.run(_ensure_webapp_ai_allowed(user, usage))

    assert usage.paid_checked is True
    assert usage.trial_checked is False
    assert asyncio.run(_remaining_ai_for_webapp(user, usage)) == 12
