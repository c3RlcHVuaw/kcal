from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import AIUsage, User
from kcal_tracker.services.growth import GrowthService


class AILimitReachedError(RuntimeError):
    pass


class AIUsageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def today_count(self, user: User) -> int:
        usage_date = self._today(user)
        result = await self.session.execute(
            select(AIUsage).where(
                AIUsage.user_id == user.id,
                AIUsage.usage_date == usage_date,
            )
        )
        return sum(item.request_count for item in result.scalars())

    async def lifetime_count(self, user: User) -> int:
        result = await self.session.execute(
            select(AIUsage).where(
                AIUsage.user_id == user.id,
            )
        )
        return sum(item.request_count for item in result.scalars())

    async def remaining_today(self, user: User) -> int:
        return max(settings.ai_daily_request_limit - await self.today_count(user), 0)

    async def remaining_trial(self, user: User) -> int:
        return max(settings.ai_trial_request_limit - await self.lifetime_count(user), 0)

    async def ensure_allowed(self, user: User, request_count: int = 1) -> None:
        if settings.ai_daily_request_limit == 0:
            raise AILimitReachedError("AI requests are disabled")
        if await self.remaining_today(user) < request_count:
            raise AILimitReachedError("Daily AI request limit reached")

    async def ensure_trial_allowed(self, user: User, request_count: int = 1) -> None:
        if settings.ai_daily_request_limit == 0:
            raise AILimitReachedError("AI requests are disabled")
        if settings.ai_trial_request_limit == 0:
            raise AILimitReachedError("AI trial requests are disabled")
        if await self.remaining_today(user) < request_count:
            raise AILimitReachedError("Daily AI request limit reached")
        if await self.remaining_trial(user) < request_count:
            raise AILimitReachedError("AI trial request limit reached")

    async def record_request(
        self,
        user: User,
        request_type: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        usage_date = self._today(user)
        result = await self.session.execute(
            select(AIUsage).where(
                AIUsage.user_id == user.id,
                AIUsage.usage_date == usage_date,
                AIUsage.request_type == request_type,
            )
        )
        usage = result.scalar_one_or_none()
        if usage is None:
            usage = AIUsage(
                user_id=user.id,
                usage_date=usage_date,
                request_type=request_type,
                request_count=0,
                input_tokens=0,
                output_tokens=0,
            )
            self.session.add(usage)

        usage.request_count += 1
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        await self.session.commit()
        await GrowthService(self.session).reward_referrer_for_activity(user)

    def _today(self, user: User) -> date:
        return datetime.now(ZoneInfo(user.timezone)).date()
