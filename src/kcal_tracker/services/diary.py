from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import ActivityLog, FoodEntry, QualityEvent, User
from kcal_tracker.schemas import DiarySummary, FoodEntryCreate, FoodEstimate
from kcal_tracker.services.food_insights import enrich_food_payload, food_advice, food_emoji
from kcal_tracker.services.growth import GrowthService
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


@dataclass(frozen=True)
class NutritionPatterns:
    tracked_days: int
    average_evening_kcal: float
    no_breakfast_days: int
    no_breakfast_over_target_days: int
    sweet_drink_days: int
    sweet_drink_average_delta: float


class DiaryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_entry(self, user: User, payload: FoodEntryCreate) -> FoodEntry:
        payload = enrich_food_payload(payload)
        entry = FoodEntry(
            user_id=user.id,
            food_name=payload.name,
            kcal=round(payload.kcal, 1),
            protein=round(payload.protein, 1),
            fat=round(payload.fat, 1),
            carbs=round(payload.carbs, 1),
            weight_g=round(payload.weight_g, 1) if payload.weight_g is not None else None,
            emoji=payload.emoji,
            advice=payload.advice,
            source=payload.source,
            confidence=payload.confidence,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        await GrowthService(self.session).reward_referrer_for_activity(user)
        return entry

    async def recent_duplicate_entry(
        self,
        user: User,
        payload: FoodEntryCreate,
        *,
        seconds: int = 10,
    ) -> FoodEntry | None:
        since = datetime.now(UTC) - timedelta(seconds=seconds)
        result = await self.session.execute(
            select(FoodEntry)
            .where(
                FoodEntry.user_id == user.id,
                FoodEntry.created_at >= since,
                FoodEntry.food_name == payload.name,
                FoodEntry.source == payload.source,
            )
            .order_by(FoodEntry.created_at.desc())
            .limit(5)
        )
        target_kcal = round(payload.kcal, 1)
        target_weight = round(payload.weight_g, 1) if payload.weight_g is not None else None
        for entry in result.scalars():
            if round(entry.kcal, 1) != target_kcal:
                continue
            entry_weight = round(entry.weight_g, 1) if entry.weight_g is not None else None
            if entry_weight == target_weight:
                return entry
        return None

    async def repeat_entry(self, user: User, entry_id: int) -> FoodEntry | None:
        entry = await self.session.get(FoodEntry, entry_id)
        if entry is None or entry.user_id != user.id:
            return None
        return await self.add_entry(user, self._payload_from_entry(entry))

    async def latest_entry(self, user: User) -> FoodEntry | None:
        result = await self.session.execute(
            select(FoodEntry)
            .where(FoodEntry.user_id == user.id)
            .order_by(FoodEntry.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def delete_latest_entry(self, user: User) -> FoodEntry | None:
        entry = await self.latest_entry(user)
        if entry is None:
            return None
        label = FoodEntry(
            user_id=entry.user_id,
            food_name=entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
            weight_g=entry.weight_g,
            emoji=entry.emoji,
            advice=entry.advice,
            source=entry.source,
            confidence=entry.confidence,
        )
        await self.session.delete(entry)
        await self.session.commit()
        return label

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

    async def update_entry_estimate(
        self,
        user: User,
        entry_id: int,
        estimate: FoodEstimate,
    ) -> FoodEntry | None:
        entry = await self.get_entry(user, entry_id)
        if entry is None:
            return None
        estimate = enrich_food_payload(estimate)
        entry.food_name = estimate.name
        entry.kcal = round(estimate.kcal, 1)
        entry.protein = round(estimate.protein, 1)
        entry.fat = round(estimate.fat, 1)
        entry.carbs = round(estimate.carbs, 1)
        entry.weight_g = round(estimate.weight_g, 1) if estimate.weight_g is not None else None
        entry.emoji = estimate.emoji
        entry.advice = estimate.advice
        entry.confidence = estimate.confidence
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def update_entry_name(
        self,
        user: User,
        entry_id: int,
        name: str,
    ) -> FoodEntry | None:
        entry = await self.get_entry(user, entry_id)
        if entry is None:
            return None
        entry.food_name = name.strip()
        entry.emoji = food_emoji(entry.food_name)
        entry.advice = food_advice(
            entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
        )
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def update_entry_kcal(
        self,
        user: User,
        entry_id: int,
        kcal: float,
    ) -> FoodEntry | None:
        entry = await self.get_entry(user, entry_id)
        if entry is None:
            return None
        old_kcal = entry.kcal or 0
        if old_kcal > 0:
            ratio = kcal / old_kcal
            entry.protein = round(entry.protein * ratio, 1)
            entry.fat = round(entry.fat * ratio, 1)
            entry.carbs = round(entry.carbs * ratio, 1)
        entry.kcal = round(kcal, 1)
        entry.advice = food_advice(
            entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
        )
        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def update_entry_macros(
        self,
        user: User,
        entry_id: int,
        protein: float,
        fat: float,
        carbs: float,
    ) -> FoodEntry | None:
        entry = await self.get_entry(user, entry_id)
        if entry is None:
            return None
        entry.protein = round(protein, 1)
        entry.fat = round(fat, 1)
        entry.carbs = round(carbs, 1)
        entry.advice = food_advice(
            entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
        )
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
                emoji=entry.emoji or food_emoji(entry.food_name),
                advice=entry.advice
                or food_advice(
                    entry.food_name,
                    kcal=entry.kcal,
                    protein=entry.protein,
                    fat=entry.fat,
                    carbs=entry.carbs,
                ),
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
        return await self.summary_for_day_offset(user, days_ago=0)

    async def summary_for_day_offset(self, user: User, days_ago: int) -> DiarySummary:
        entries = await self.entries_for_day_offset(user, days_ago=days_ago)
        activity_kcal = await self.activity_kcal_for_day_offset(user, days_ago=days_ago)
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

    async def recent_matching_entry(self, user: User, text: str) -> FoodEntry | None:
        query = _normalize_food_query(text)
        if len(query) < 3:
            return None

        learned = await self._learned_matching_entry(user, query)
        if learned is not None:
            return learned

        result = await self.session.execute(
            select(FoodEntry)
            .where(FoodEntry.user_id == user.id)
            .order_by(FoodEntry.created_at.desc())
            .limit(200)
        )
        for entry in result.scalars():
            entry_query = _normalize_food_query(entry.food_name)
            if not entry_query:
                continue
            if _matches_food_history_query(query, entry_query):
                return entry
        return None

    async def _learned_matching_entry(self, user: User, query: str) -> FoodEntry | None:
        result = await self.session.execute(
            select(QualityEvent)
            .where(
                QualityEvent.user_id == user.id,
                QualityEvent.event_type == "food_learned",
            )
            .order_by(QualityEvent.created_at.desc())
            .limit(100)
        )
        for event in result.scalars():
            event_query = _normalize_food_query(event.query or "")
            if not event_query or not _matches_food_history_query(query, event_query):
                continue
            entry_id = (event.details or {}).get("entry_id")
            if not entry_id:
                continue
            entry = await self.get_entry(user, int(entry_id))
            if entry is not None:
                return entry
        return None

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
                created_at = created_at.replace(tzinfo=UTC)
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

    async def nutrition_patterns(self, user: User, days: int = 21) -> NutritionPatterns:
        tz = ZoneInfo(user.timezone)
        today = datetime.now(tz).date()
        start_date = today.fromordinal(today.toordinal() - days)
        start = datetime.combine(start_date, time.min, tzinfo=tz)
        end = datetime.combine(today, time.min, tzinfo=tz)

        result = await self.session.execute(
            select(FoodEntry)
            .where(
                FoodEntry.user_id == user.id,
                FoodEntry.created_at >= start,
                FoodEntry.created_at < end,
            )
            .order_by(FoodEntry.created_at.asc())
        )

        entries_by_date: dict[date, list[FoodEntry]] = defaultdict(list)
        for entry in result.scalars():
            created_at = _as_user_time(entry.created_at, tz)
            entries_by_date[created_at.date()].append(entry)

        day_kcal: list[float] = []
        evening_kcal: list[float] = []
        no_breakfast_days = 0
        no_breakfast_over_target_days = 0
        sweet_drink_day_kcal: list[float] = []
        no_sweet_drink_day_kcal: list[float] = []

        for entries in entries_by_date.values():
            total = sum(entry.kcal for entry in entries)
            if total <= 0:
                continue

            day_kcal.append(total)
            has_breakfast = False
            has_sweet_drink = False
            evening_total = 0.0
            for entry in entries:
                created_at = _as_user_time(entry.created_at, tz)
                if created_at.hour < 12:
                    has_breakfast = True
                if created_at.hour >= 18:
                    evening_total += entry.kcal
                if _looks_like_sweet_drink(entry.food_name):
                    has_sweet_drink = True

            if evening_total:
                evening_kcal.append(evening_total)
            if not has_breakfast:
                no_breakfast_days += 1
                if total > user.daily_kcal_target + 150:
                    no_breakfast_over_target_days += 1
            if has_sweet_drink:
                sweet_drink_day_kcal.append(total)
            else:
                no_sweet_drink_day_kcal.append(total)

        sweet_drink_delta = 0.0
        if sweet_drink_day_kcal and no_sweet_drink_day_kcal:
            sweet_drink_delta = _average(sweet_drink_day_kcal) - _average(
                no_sweet_drink_day_kcal
            )

        return NutritionPatterns(
            tracked_days=len(day_kcal),
            average_evening_kcal=_average(evening_kcal),
            no_breakfast_days=no_breakfast_days,
            no_breakfast_over_target_days=no_breakfast_over_target_days,
            sweet_drink_days=len(sweet_drink_day_kcal),
            sweet_drink_average_delta=sweet_drink_delta,
        )

    def _payload_from_entry(self, entry: FoodEntry) -> FoodEntryCreate:
        return FoodEntryCreate(
            name=entry.food_name,
            kcal=entry.kcal,
            protein=entry.protein,
            fat=entry.fat,
            carbs=entry.carbs,
            weight_g=entry.weight_g,
            emoji=entry.emoji,
            advice=entry.advice,
            confidence=entry.confidence,
            source=entry.source,
        )


def estimate_from_entry(entry: FoodEntry) -> FoodEstimate:
    return FoodEstimate(
        name=entry.food_name,
        kcal=entry.kcal,
        protein=entry.protein,
        fat=entry.fat,
        carbs=entry.carbs,
        weight_g=entry.weight_g,
        emoji=entry.emoji,
        advice=entry.advice,
        confidence=entry.confidence,
    )


def _normalize_food_query(text: str) -> str:
    value = text.casefold()
    value = re.sub(r"\d+(?:[,.]\d+)?", " ", value)
    value = re.sub(r"\b(?:г|гр|грамм|граммов|кг|мл|л|ккал|кал)\b", " ", value)
    value = re.sub(r"[^a-zа-яё0-9]+", " ", value)
    return " ".join(value.split())


def _matches_food_history_query(query: str, entry_query: str) -> bool:
    if query == entry_query or query in entry_query:
        return True
    query_words = set(query.split())
    entry_words = set(entry_query.split())
    return bool(query_words and entry_words and query_words.issubset(entry_words))


def _as_user_time(value: datetime, tz: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(tz)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _looks_like_sweet_drink(name: str) -> bool:
    lowered = name.casefold()
    return any(
        term in lowered
        for term in (
            "сок",
            "кола",
            "газиров",
            "лимонад",
            "морс",
            "компот",
            "энергетик",
            "милкшейк",
            "молочный коктейль",
            "сироп",
            "сладкий напит",
        )
    )
