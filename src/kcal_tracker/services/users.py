from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.models import User


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get_or_create(self, telegram_id: int, username: str | None) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            if username and user.username != username:
                user.username = username
                await self.session.commit()
                await self.session.refresh(user)
            return user

        user = User(
            telegram_id=telegram_id,
            username=username,
            timezone=settings.default_timezone,
            daily_kcal_target=settings.default_daily_kcal_target,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

