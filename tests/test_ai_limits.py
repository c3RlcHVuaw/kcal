from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

from kcal_tracker.api import routes
from kcal_tracker.api.routes import (
    _ai_usage_summary,
    _ensure_webapp_ai_allowed,
    _remaining_ai_for_webapp,
)
from kcal_tracker.models import User
from kcal_tracker.services import ai_usage
from kcal_tracker.services.ai_queue import _try_acquire_slot
from kcal_tracker.services.ai_usage import AILimitReachedError, AIUsageService
from kcal_tracker.services.throttle import ThrottleLimitReached


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


class FakeRedisSlots:
    def __init__(self, occupied: set[str] | None = None) -> None:
        self.occupied = occupied or set()
        self.set_calls: list[tuple[str, str, int, bool]] = []

    async def set(self, key: str, token: str, *, ex: int, nx: bool) -> bool:
        self.set_calls.append((key, token, ex, nx))
        if key in self.occupied:
            return False
        self.occupied.add(key)
        return True


def test_webapp_free_ai_summary_uses_trial_remaining() -> None:
    user = User(id=1, telegram_id=1001)
    usage = FakeUsageService(used_today=1, lifetime_used=2, remaining_today=29, remaining_trial=1)

    summary = asyncio.run(_ai_usage_summary(user, usage))

    assert summary.is_trial is True
    assert summary.trial_used == 2
    assert summary.trial_limit == 3
    assert summary.trial_remaining == 1
    assert summary.remaining_today == 1


def test_ai_photo_queue_acquires_first_free_slot(monkeypatch) -> None:
    redis = FakeRedisSlots(occupied={"ai:photo:slot:0"})
    monkeypatch.setattr(routes.settings, "ai_photo_queue_concurrency", 2)
    monkeypatch.setattr(routes.settings, "ai_photo_queue_slot_ttl_seconds", 30)

    key = asyncio.run(_try_acquire_slot(redis, "token", "user-1"))

    assert key == "ai:photo:slot:1"
    assert redis.set_calls[-1] == ("ai:photo:slot:1", "token", 30, True)


def test_ai_photo_queue_returns_none_when_full(monkeypatch) -> None:
    redis = FakeRedisSlots(occupied={"ai:photo:slot:0", "ai:photo:slot:1"})
    monkeypatch.setattr(routes.settings, "ai_photo_queue_concurrency", 2)

    key = asyncio.run(_try_acquire_slot(redis, "token", "user-1"))

    assert key is None


def test_webapp_free_ai_check_uses_trial_limit(monkeypatch) -> None:
    user = User(id=1, telegram_id=1001)
    usage = FakeUsageService(remaining_today=29, remaining_trial=1)
    called = []

    async def ok_throttle(telegram_id: int, action: str) -> None:
        called.append((telegram_id, action))

    monkeypatch.setattr(routes, "ensure_ai_rate_limit", ok_throttle)

    asyncio.run(_ensure_webapp_ai_allowed(user, usage))

    assert usage.trial_checked is True
    assert usage.paid_checked is False
    assert called == [(1001, "webapp_ai")]
    assert asyncio.run(_remaining_ai_for_webapp(user, usage)) == 1


def test_webapp_paid_ai_check_uses_plan_daily_limit(monkeypatch) -> None:
    user = User(
        id=1,
        telegram_id=1001,
        subscription_expires_at=datetime.now(UTC) + timedelta(days=1),
        subscription_plan="basic",
    )
    usage = FakeUsageService(remaining_today=12, remaining_trial=0)

    async def ok_throttle(telegram_id: int, action: str) -> None:
        return None

    monkeypatch.setattr(routes, "ensure_ai_rate_limit", ok_throttle)

    asyncio.run(_ensure_webapp_ai_allowed(user, usage))

    assert usage.paid_checked is True
    assert usage.trial_checked is False
    assert asyncio.run(_remaining_ai_for_webapp(user, usage)) == 12


def test_unlimited_ai_safety_limit_can_stop_expensive_user(monkeypatch) -> None:
    user = User(id=1, telegram_id=1001)
    service = AIUsageService.__new__(AIUsageService)

    async def remaining_today(_user: User) -> int:
        return 0

    monkeypatch.setattr(ai_usage, "user_ai_daily_limit", lambda _user: None)
    monkeypatch.setattr(ai_usage.settings, "ai_unlimited_safety_daily_request_limit", 120)
    monkeypatch.setattr(service, "remaining_today", remaining_today)

    try:
        asyncio.run(service.ensure_allowed(user))
    except AILimitReachedError:
        pass
    else:
        raise AssertionError("Safety limit did not stop unlimited AI usage")


def test_webapp_ai_check_maps_throttle_to_429(monkeypatch) -> None:
    user = User(id=1, telegram_id=1001)
    usage = FakeUsageService(remaining_today=29, remaining_trial=1)

    async def blocked_throttle(telegram_id: int, action: str) -> None:
        raise ThrottleLimitReached(17)

    monkeypatch.setattr(routes, "ensure_ai_rate_limit", blocked_throttle)

    try:
        asyncio.run(_ensure_webapp_ai_allowed(user, usage, action="webapp_photo"))
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.headers == {"Retry-After": "17"}
    else:
        raise AssertionError("Throttle did not raise HTTPException")
