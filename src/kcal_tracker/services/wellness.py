from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import (
    ActivityLog,
    AppleHealthDailySync,
    FavoriteFood,
    FoodEntry,
    User,
    WaterLog,
    WeightLog,
)
from kcal_tracker.schemas import ActivityEstimate, FoodEntryCreate
from kcal_tracker.services.food_insights import enrich_food_payload, food_advice, food_emoji
from kcal_tracker.services.growth import GrowthService


@dataclass(frozen=True)
class WeightTrend:
    logs: list[WeightLog]
    latest_kg: float | None
    average_7d_kg: float | None
    delta_7d_kg: float | None
    trend_label: str


@dataclass(frozen=True)
class HabitSummary:
    food_streak_days: int
    water_streak_days: int
    weight_streak_days: int
    tracked_food_days_30: int
    tracked_water_days_30: int
    tracked_weight_days_30: int
    best_habit: str


class WellnessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_water(self, user: User, amount_ml: int) -> WaterLog:
        log = WaterLog(user_id=user.id, amount_ml=amount_ml)
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        await GrowthService(self.session).reward_referrer_for_activity(user)
        return log

    async def today_water_ml(self, user: User) -> int:
        return await self.water_ml_for_day_offset(user, days_ago=0)

    async def water_ml_for_day_offset(self, user: User, days_ago: int) -> int:
        result = await self.session.execute(
            select(WaterLog).where(
                WaterLog.user_id == user.id,
                WaterLog.created_at >= self._day_start(user, days_ago=days_ago),
                WaterLog.created_at <= self._day_end(user, days_ago=days_ago),
            )
        )
        return sum(log.amount_ml for log in result.scalars())

    async def add_weight(self, user: User, weight_kg: float) -> WeightLog:
        user.weight = weight_kg
        log = WeightLog(user_id=user.id, weight_kg=weight_kg)
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        await GrowthService(self.session).reward_referrer_for_activity(user)
        return log

    async def latest_weight(self, user: User) -> WeightLog | None:
        result = await self.session.execute(
            select(WeightLog)
            .where(WeightLog.user_id == user.id)
            .order_by(WeightLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def weight_history(self, user: User, days: int = 30) -> list[WeightLog]:
        tz = ZoneInfo(user.timezone)
        today = datetime.now(tz).date()
        start_date = today.fromordinal(today.toordinal() - days + 1)
        start = datetime.combine(start_date, time.min, tzinfo=tz)
        result = await self.session.execute(
            select(WeightLog)
            .where(
                WeightLog.user_id == user.id,
                WeightLog.created_at >= start,
            )
            .order_by(WeightLog.created_at.asc())
        )
        return list(result.scalars())

    async def weight_trend(self, user: User, days: int = 30) -> WeightTrend:
        logs = await self.weight_history(user, days=days)
        if not logs:
            return WeightTrend(
                logs=[],
                latest_kg=None,
                average_7d_kg=None,
                delta_7d_kg=None,
                trend_label="пока нет данных",
            )

        tz = ZoneInfo(user.timezone)
        latest = logs[-1]
        latest_date = _as_user_date(latest.created_at, tz)
        window_start = latest_date.fromordinal(latest_date.toordinal() - 6)
        recent = [
            log
            for log in logs
            if _as_user_date(log.created_at, tz) >= window_start
        ]
        average_7d = sum(log.weight_kg for log in recent) / len(recent)
        previous = next(
            (
                log
                for log in reversed(logs)
                if _as_user_date(log.created_at, tz) <= window_start
            ),
            logs[0] if len(logs) > 1 else None,
        )
        delta = latest.weight_kg - previous.weight_kg if previous is not None else 0.0
        return WeightTrend(
            logs=logs,
            latest_kg=latest.weight_kg,
            average_7d_kg=average_7d,
            delta_7d_kg=delta,
            trend_label=_trend_label(delta),
        )

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
        await GrowthService(self.session).reward_referrer_for_activity(user)
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

    async def today_activities(self, user: User) -> list[ActivityLog]:
        return await self.activities_for_day_offset(user, days_ago=0)

    async def activities_for_day_offset(self, user: User, days_ago: int) -> list[ActivityLog]:
        result = await self.session.execute(
            select(ActivityLog)
            .where(
                ActivityLog.user_id == user.id,
                ActivityLog.created_at >= self._day_start(user, days_ago=days_ago),
                ActivityLog.created_at <= self._day_end(user, days_ago=days_ago),
            )
            .order_by(ActivityLog.created_at.asc())
        )
        return list(result.scalars())

    async def delete_activity(self, user: User, activity_id: int) -> ActivityLog | None:
        activity = await self.session.get(ActivityLog, activity_id)
        if activity is None or activity.user_id != user.id:
            return None
        await self.session.delete(activity)
        if activity.source == "apple_health":
            metric = "steps" if "steps" in activity.activity_name.lower() else "active_kcal"
            await self._delete_apple_health_sync(user, metric)
        await self.session.commit()
        return activity

    async def apple_health_delta(self, user: User, metric: str, value: float) -> float:
        sync_date = datetime.now(ZoneInfo(user.timezone)).date()
        result = await self.session.execute(
            select(AppleHealthDailySync).where(
                AppleHealthDailySync.user_id == user.id,
                AppleHealthDailySync.sync_date == sync_date,
                AppleHealthDailySync.metric == metric,
            )
        )
        sync = result.scalar_one_or_none()
        if sync is None:
            sync = AppleHealthDailySync(
                user_id=user.id,
                sync_date=sync_date,
                metric=metric,
                value=value,
            )
            self.session.add(sync)
            await self.session.commit()
            return max(value, 0)

        delta = value - sync.value
        if value > sync.value:
            sync.value = value
            await self.session.commit()
            return delta
        return 0

    async def _delete_apple_health_sync(self, user: User, metric: str) -> None:
        sync_date = datetime.now(ZoneInfo(user.timezone)).date()
        result = await self.session.execute(
            select(AppleHealthDailySync).where(
                AppleHealthDailySync.user_id == user.id,
                AppleHealthDailySync.sync_date == sync_date,
                AppleHealthDailySync.metric == metric,
            )
        )
        sync = result.scalar_one_or_none()
        if sync is not None:
            await self.session.delete(sync)

    async def habit_summary(self, user: User, days: int = 30) -> HabitSummary:
        tz = ZoneInfo(user.timezone)
        today = datetime.now(tz).date()
        dates = [today.fromordinal(today.toordinal() - offset) for offset in range(days)]
        start = datetime.combine(dates[-1], time.min, tzinfo=tz)
        end = datetime.combine(today, time.max, tzinfo=tz)

        food_dates = await self._log_dates(FoodEntry, user, start, end, tz)
        water_dates = await self._log_dates(WaterLog, user, start, end, tz)
        weight_dates = await self._log_dates(WeightLog, user, start, end, tz)

        food_streak = _current_streak(dates, food_dates)
        water_streak = _current_streak(dates, water_dates)
        weight_streak = _current_streak(dates, weight_dates)
        best_habit = max(
            (
                ("еда", food_streak),
                ("вода", water_streak),
                ("вес", weight_streak),
            ),
            key=lambda item: item[1],
        )[0]
        return HabitSummary(
            food_streak_days=food_streak,
            water_streak_days=water_streak,
            weight_streak_days=weight_streak,
            tracked_food_days_30=len(food_dates),
            tracked_water_days_30=len(water_dates),
            tracked_weight_days_30=len(weight_dates),
            best_habit=best_habit if max(food_streak, water_streak, weight_streak) else "еда",
        )

    async def add_favorite_from_entry(self, user: User, entry: FoodEntry) -> FavoriteFood:
        favorite = FavoriteFood(
            user_id=user.id,
            food_name=entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
            weight_g=entry.weight_g,
            emoji=entry.emoji or food_emoji(entry.food_name),
            advice=entry.advice
            or food_advice(
                entry.food_name,
                kcal=entry.kcal,
                protein=entry.protein,
                fat=entry.fat,
                carbs=entry.carbs,
            ),
        )
        self.session.add(favorite)
        await self.session.commit()
        await self.session.refresh(favorite)
        return favorite

    async def add_favorite(self, user: User, payload: FoodEntryCreate) -> FavoriteFood:
        payload = enrich_food_payload(payload)
        favorite = FavoriteFood(
            user_id=user.id,
            food_name=payload.name,
            kcal=round(payload.kcal, 1),
            protein=round(payload.protein, 1),
            fat=round(payload.fat, 1),
            carbs=round(payload.carbs, 1),
            weight_g=round(payload.weight_g, 1) if payload.weight_g is not None else None,
            emoji=payload.emoji,
            advice=payload.advice,
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
            emoji=favorite.emoji,
            advice=favorite.advice,
            confidence=None,
            source="manual",
        )

    def _day_start(self, user: User, *, days_ago: int = 0) -> datetime:
        tz = ZoneInfo(user.timezone)
        target_date = datetime.now(tz).date()
        if days_ago:
            target_date = target_date.fromordinal(target_date.toordinal() - days_ago)
        return datetime.combine(target_date, time.min, tzinfo=tz)

    def _day_end(self, user: User, *, days_ago: int = 0) -> datetime:
        tz = ZoneInfo(user.timezone)
        target_date = datetime.now(tz).date()
        if days_ago:
            target_date = target_date.fromordinal(target_date.toordinal() - days_ago)
        return datetime.combine(target_date, time.max, tzinfo=tz)

    async def _log_dates(self, model, user: User, start: datetime, end: datetime, tz: ZoneInfo):
        result = await self.session.execute(
            select(model.created_at).where(
                model.user_id == user.id,
                model.created_at >= start,
                model.created_at <= end,
            )
        )
        return {_as_user_date(created_at, tz) for created_at in result.scalars()}


def _as_user_date(value: datetime, tz: ZoneInfo) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz).date()


def _trend_label(delta_kg: float) -> str:
    if delta_kg <= -0.3:
        return "снижается"
    if delta_kg >= 0.3:
        return "растёт"
    return "стабилен"


def _current_streak(dates_desc: list[date], log_dates: set[date]) -> int:
    streak = 0
    for day in dates_desc:
        if day not in log_dates:
            if streak == 0 and day == dates_desc[0]:
                continue
            break
        streak += 1
    return streak
