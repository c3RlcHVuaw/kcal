from __future__ import annotations

import csv
from io import StringIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import ActivityLog, FoodEntry, User, WaterLog, WeightLog


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def food_csv(self, user: User) -> str:
        result = await self.session.execute(
            select(FoodEntry)
            .where(FoodEntry.user_id == user.id)
            .order_by(FoodEntry.created_at.asc())
        )
        rows = [
            [
                entry.created_at.isoformat(),
                entry.food_name,
                entry.weight_g or "",
                entry.kcal,
                entry.protein,
                entry.fat,
                entry.carbs,
                entry.source,
                entry.confidence if entry.confidence is not None else "",
            ]
            for entry in result.scalars()
        ]
        return _csv(
            [
                "created_at",
                "name",
                "weight_g",
                "kcal",
                "protein",
                "fat",
                "carbs",
                "source",
                "confidence",
            ],
            rows,
        )

    async def wellness_csv(self, user: User) -> str:
        water_result = await self.session.execute(
            select(WaterLog)
            .where(WaterLog.user_id == user.id)
            .order_by(WaterLog.created_at.asc())
        )
        weight_result = await self.session.execute(
            select(WeightLog)
            .where(WeightLog.user_id == user.id)
            .order_by(WeightLog.created_at.asc())
        )
        activity_result = await self.session.execute(
            select(ActivityLog)
            .where(ActivityLog.user_id == user.id)
            .order_by(ActivityLog.created_at.asc())
        )

        rows: list[list[object]] = []
        rows.extend(
            [log.created_at.isoformat(), "water", log.amount_ml, "ml", ""]
            for log in water_result.scalars()
        )
        rows.extend(
            [log.created_at.isoformat(), "weight", log.weight_kg, "kg", ""]
            for log in weight_result.scalars()
        )
        rows.extend(
            [
                log.created_at.isoformat(),
                "activity",
                log.kcal,
                "kcal",
                log.activity_name,
            ]
            for log in activity_result.scalars()
        )
        rows.sort(key=lambda row: str(row[0]))
        return _csv(["created_at", "kind", "value", "unit", "note"], rows)


def _csv(header: list[str], rows: list[list[object]]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue()
