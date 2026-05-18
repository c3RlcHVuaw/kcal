from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import ActivityLog, FavoriteFood, FoodEntry, User, WaterLog, WeightLog
from kcal_tracker.schemas import ActivityEstimate, FoodEntryCreate


class WellnessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_water(self, user: User, amount_ml: int) -> WaterLog:
        log = WaterLog(user_id=user.id, amount_ml=amount_ml)
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def today_water_ml(self, user: User) -> int:
        result = await self.session.execute(
            select(WaterLog).where(
                WaterLog.user_id == user.id,
                WaterLog.created_at >= self._day_start(user),
                WaterLog.created_at <= self._day_end(user),
            )
        )
        return sum(log.amount_ml for log in result.scalars())

    async def add_weight(self, user: User, weight_kg: float) -> WeightLog:
        user.weight = weight_kg
        log = WeightLog(user_id=user.id, weight_kg=weight_kg)
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def latest_weight(self, user: User) -> WeightLog | None:
        result = await self.session.execute(
            select(WeightLog)
            .where(WeightLog.user_id == user.id)
            .order_by(WeightLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def add_activity(
        self,
        user: User,
        estimate: ActivityEstimate,
        source: str,
    ) -> ActivityLog:
        log = ActivityLog(
            user_id=user.id,
            activity_name=estimate.name,
            kcal=round(estimate.kcal, 1),
            source=source,
            confidence=estimate.confidence,
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def today_activity_kcal(self, user: User) -> float:
        result = await self.session.execute(
            select(ActivityLog).where(
                ActivityLog.user_id == user.id,
                ActivityLog.created_at >= self._day_start(user),
                ActivityLog.created_at <= self._day_end(user),
            )
        )
        return sum(log.kcal for log in result.scalars())

    async def add_favorite_from_entry(self, user: User, entry: FoodEntry) -> FavoriteFood:
        favorite = FavoriteFood(
            user_id=user.id,
            food_name=entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
            weight_g=entry.weight_g,
        )
        self.session.add(favorite)
        await self.session.commit()
        await self.session.refresh(favorite)
        return favorite

    async def add_favorite(self, user: User, payload: FoodEntryCreate) -> FavoriteFood:
        favorite = FavoriteFood(
            user_id=user.id,
            food_name=payload.name,
            kcal=round(payload.kcal, 1),
            protein=round(payload.protein, 1),
            fat=round(payload.fat, 1),
            carbs=round(payload.carbs, 1),
            weight_g=round(payload.weight_g, 1) if payload.weight_g is not None else None,
        )
        self.session.add(favorite)
        await self.session.commit()
        await self.session.refresh(favorite)
        return favorite

    async def favorites(self, user: User, limit: int = 20) -> list[FavoriteFood]:
        result = await self.session.execute(
            select(FavoriteFood)
            .where(FavoriteFood.user_id == user.id)
            .order_by(FavoriteFood.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def favorite(self, user: User, favorite_id: int) -> FavoriteFood | None:
        favorite = await self.session.get(FavoriteFood, favorite_id)
        if favorite is None or favorite.user_id != user.id:
            return None
        return favorite

    async def delete_favorite(self, user: User, favorite_id: int) -> bool:
        favorite = await self.favorite(user, favorite_id)
        if favorite is None:
            return False
        await self.session.delete(favorite)
        await self.session.commit()
        return True

    def favorite_payload(self, favorite: FavoriteFood) -> FoodEntryCreate:
        return FoodEntryCreate(
            name=favorite.food_name,
            kcal=favorite.kcal,
            protein=favorite.protein,
            fat=favorite.fat,
            carbs=favorite.carbs,
            weight_g=favorite.weight_g,
            confidence=None,
            source="manual",
        )

    def _day_start(self, user: User) -> datetime:
        tz = ZoneInfo(user.timezone)
        return datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz)

    def _day_end(self, user: User) -> datetime:
        tz = ZoneInfo(user.timezone)
        return datetime.combine(datetime.now(tz).date(), time.max, tzinfo=tz)
