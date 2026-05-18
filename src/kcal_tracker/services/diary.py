from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import ActivityLog, FoodEntry, User
from kcal_tracker.schemas import DiarySummary, FoodEntryCreate
from kcal_tracker.services.profile import calculate_macro_targets


@dataclass(frozen=True)
class FrequentFood:
    entry: FoodEntry
    count: int


@dataclass(frozen=True)
class DailyNutrition:
    date_label: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    entries_count: int


@dataclass(frozen=True)
class WeeklyAnalytics:
    days: list[DailyNutrition]
    average_kcal: float
    target_kcal: int
    days_in_target: int


class DiaryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_entry(self, user: User, payload: FoodEntryCreate) -> FoodEntry:
        entry = FoodEntry(
            user_id=user.id,
            food_name=payload.name,
            kcal=round(payload.kcal, 1),
            protein=round(payload.protein, 1),
            fat=round(payload.fat, 1),
            carbs=round(payload.carbs, 1),
            weight_g=round(payload.weight_g, 1) if payload.weight_g is not None else None,
            source=payload.source,
            confidence=payload.confidence,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def repeat_entry(self, user: User, entry_id: int) -> FoodEntry | None:
        entry = await self.session.get(FoodEntry, entry_id)
        if entry is None or entry.user_id != user.id:
            return None
        return await self.add_entry(user, self._payload_from_entry(entry))

    async def get_entry(self, user: User, entry_id: int) -> FoodEntry | None:
        entry = await self.session.get(FoodEntry, entry_id)
        if entry is None or entry.user_id != user.id:
            return None
        return entry

    async def delete_entry(self, user: User, entry_id: int) -> bool:
        entry = await self.get_entry(user, entry_id)
        if entry is None:
            return False
        await self.session.delete(entry)
        await self.session.commit()
        return True

    async def update_entry_weight(
        self,
        user: User,
        entry_id: int,
        weight_g: float,
    ) -> FoodEntry | None:
        entry = await self.get_entry(user, entry_id)
        if entry is None:
            return None
        old_weight = entry.weight_g or 0
        if old_weight > 0:
            ratio = weight_g / old_weight
            entry.kcal = round(entry.kcal * ratio, 1)
            entry.protein = round(entry.protein * ratio, 1)
            entry.fat = round(entry.fat * ratio, 1)
            entry.carbs = round(entry.carbs * ratio, 1)
        entry.weight_g = round(weight_g, 1)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def repeat_yesterday(self, user: User) -> list[FoodEntry]:
        entries = await self.entries_for_day_offset(user, days_ago=1)
        repeated = [
            FoodEntry(
                user_id=user.id,
                food_name=entry.food_name,
                kcal=entry.kcal,
                protein=entry.protein,
                fat=entry.fat,
                carbs=entry.carbs,
                weight_g=entry.weight_g,
                source=entry.source,
                confidence=entry.confidence,
            )
            for entry in entries
        ]
        self.session.add_all(repeated)
        await self.session.commit()
        for entry in repeated:
            await self.session.refresh(entry)
        return repeated

    async def today_summary(self, user: User) -> DiarySummary:
        entries = await self.entries_for_day_offset(user, days_ago=0)
        activity_kcal = await self.activity_kcal_for_day_offset(user, days_ago=0)
        protein_target, fat_target, carbs_target = calculate_macro_targets(user)
        return DiarySummary(
            kcal=sum(item.kcal for item in entries),
            protein=sum(item.protein for item in entries),
            fat=sum(item.fat for item in entries),
            carbs=sum(item.carbs for item in entries),
            activity_kcal=activity_kcal,
            base_target_kcal=user.daily_kcal_target,
            target_kcal=round(user.daily_kcal_target + activity_kcal),
            target_protein=protein_target,
            target_fat=fat_target,
            target_carbs=carbs_target,
            entries=entries,
        )

    async def entries_for_day_offset(self, user: User, days_ago: int) -> list[FoodEntry]:
        tz = ZoneInfo(user.timezone)
        target_date = datetime.now(tz).date()
        if days_ago:
            target_date = target_date.fromordinal(target_date.toordinal() - days_ago)
        start = datetime.combine(target_date, time.min, tzinfo=tz)
        end = datetime.combine(target_date, time.max, tzinfo=tz)

        result = await self.session.execute(
            select(FoodEntry)
            .where(
                FoodEntry.user_id == user.id,
                FoodEntry.created_at >= start,
                FoodEntry.created_at <= end,
            )
            .order_by(FoodEntry.created_at.asc())
        )
        return list(result.scalars())

    async def activity_kcal_for_day_offset(self, user: User, days_ago: int) -> float:
        tz = ZoneInfo(user.timezone)
        target_date = datetime.now(tz).date()
        if days_ago:
            target_date = target_date.fromordinal(target_date.toordinal() - days_ago)
        start = datetime.combine(target_date, time.min, tzinfo=tz)
        end = datetime.combine(target_date, time.max, tzinfo=tz)

        result = await self.session.execute(
            select(ActivityLog).where(
                ActivityLog.user_id == user.id,
                ActivityLog.created_at >= start,
                ActivityLog.created_at <= end,
            )
        )
        return sum(log.kcal for log in result.scalars())

    async def frequent_foods(self, user: User, limit: int = 8) -> list[FrequentFood]:
        result = await self.session.execute(
            select(FoodEntry)
            .where(FoodEntry.user_id == user.id)
            .order_by(FoodEntry.created_at.desc())
            .limit(200)
        )
        entries = list(result.scalars())
        grouped: dict[str, list[FoodEntry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.food_name.strip().casefold()].append(entry)

        frequent = [
            FrequentFood(entry=items[0], count=len(items))
            for items in grouped.values()
            if items and len(items) > 1
        ]
        frequent.sort(key=lambda item: (item.count, item.entry.created_at), reverse=True)
        return frequent[:limit]

    async def weekly_analytics(self, user: User, days: int = 7) -> WeeklyAnalytics:
        tz = ZoneInfo(user.timezone)
        today = datetime.now(tz).date()
        dates = [
            today.fromordinal(today.toordinal() - offset)
            for offset in range(days - 1, -1, -1)
        ]
        start = datetime.combine(dates[0], time.min, tzinfo=tz)
        end = datetime.combine(dates[-1], time.max, tzinfo=tz)
        result = await self.session.execute(
            select(FoodEntry)
            .where(
                FoodEntry.user_id == user.id,
                FoodEntry.created_at >= start,
                FoodEntry.created_at <= end,
            )
            .order_by(FoodEntry.created_at.asc())
        )
        entries_by_date: dict[date, list[FoodEntry]] = defaultdict(list)
        for entry in result.scalars():
            created_at = entry.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=tz)
            entries_by_date[created_at.astimezone(tz).date()].append(entry)

        day_summaries = [
            DailyNutrition(
                date_label=day.strftime("%d.%m"),
                kcal=sum(entry.kcal for entry in entries_by_date[day]),
                protein=sum(entry.protein for entry in entries_by_date[day]),
                fat=sum(entry.fat for entry in entries_by_date[day]),
                carbs=sum(entry.carbs for entry in entries_by_date[day]),
                entries_count=len(entries_by_date[day]),
            )
            for day in dates
        ]
        tracked_days = [day for day in day_summaries if day.entries_count]
        average_kcal = (
            sum(day.kcal for day in tracked_days) / len(tracked_days) if tracked_days else 0
        )
        days_in_target = sum(
            1 for day in tracked_days if abs(day.kcal - user.daily_kcal_target) <= 150
        )
        return WeeklyAnalytics(
            days=day_summaries,
            average_kcal=average_kcal,
            target_kcal=user.daily_kcal_target,
            days_in_target=days_in_target,
        )

    def _payload_from_entry(self, entry: FoodEntry) -> FoodEntryCreate:
        return FoodEntryCreate(
            name=entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
            weight_g=entry.weight_g,
            confidence=entry.confidence,
            source=entry.source,
        )
