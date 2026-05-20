from __future__ import annotations

import secrets

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

    async def get_by_apple_health_token(self, token: str) -> User | None:
        result = await self.session.execute(select(User).where(User.apple_health_token == token))
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> User | None:
        result = await self.session.execute(select(User).where(User.referral_code == code))
        return result.scalar_one_or_none()

    async def ensure_referral_code(self, user: User) -> str:
        if user.referral_code:
            return user.referral_code
        while True:
            code = _make_referral_code()
            if await self.get_by_referral_code(code) is None:
                user.referral_code = code
                await self.session.commit()
                await self.session.refresh(user)
                return code

    async def attach_referrer(self, user: User, referral_code: str | None) -> bool:
        if not referral_code or user.referred_by_user_id is not None:
            return False
        referrer = await self.get_by_referral_code(referral_code)
        if referrer is None or referrer.id == user.id:
            return False
        user.referred_by_user_id = referrer.id
        await self.session.commit()
        await self.session.refresh(user)
        return True

    async def ensure_apple_health_token(self, user: User) -> str:
        if user.apple_health_token:
            return user.apple_health_token
        while True:
            token = secrets.token_urlsafe(24)
            if await self.get_by_apple_health_token(token) is None:
                user.apple_health_token = token
                await self.session.commit()
                await self.session.refresh(user)
                return token

    async def get_or_create(self, telegram_id: int, username: str | None) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is not None:
            if username and user.username != username:
                user.username = username
                await self.session.commit()
                await self.session.refresh(user)
            return user

        while True:
            code = _make_referral_code()
            if await self.get_by_referral_code(code) is None:
                break

        user = User(
            telegram_id=telegram_id,
            username=username,
            timezone=settings.default_timezone,
            daily_kcal_target=settings.default_daily_kcal_target,
            referral_code=code,
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user


def _make_referral_code() -> str:
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
