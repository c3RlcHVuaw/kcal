from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from kcal_tracker.config import settings
from kcal_tracker.schemas import FoodEntryCreate
from kcal_tracker.services.food_insights import food_label

logger = logging.getLogger(__name__)


def day_offset_title(timezone_name: str, *, days_ago: int) -> str:
    if days_ago == 1:
        return f"📊 Вчера, {day_offset_date_label(timezone_name, days_ago=days_ago)}"
    return "📊 Сегодня"


def day_offset_date_label(timezone_name: str, *, days_ago: int) -> str:
    tz = safe_timezone(timezone_name)
    target_date = datetime.now(tz).date()
    if days_ago:
        target_date = target_date.fromordinal(target_date.toordinal() - days_ago)
    return target_date.strftime("%d.%m")


def safe_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        logger.warning("Invalid user timezone %s, falling back to default", timezone_name)
        return ZoneInfo(settings.default_timezone)


def entry_line(index: int, entry, timezone_name: str) -> str:
    weight = f", {entry.weight_g:.0f}г" if entry.weight_g else ""
    return (
        f"{index}. {entry_time_label(entry.created_at, timezone_name)} "
        f"{food_label(entry)}{weight} — {entry.kcal:.0f} ккал"
    )


def activity_management_text(activities, timezone_name: str) -> str:
    lines = ["🏃 Активность сегодня", ""]
    for index, activity in enumerate(activities, start=1):
        lines.append(activity_line(index, activity, timezone_name))
    lines.extend(["", "Нажми на запись, чтобы удалить её из дневника."])
    return "\n".join(lines)


def activity_dashboard_text(activities, timezone_name: str) -> str:
    if not activities:
        return "\n".join(
            [
                "🏃 Активность",
                "",
                "Сегодня активности пока нет.",
                "Можно добавить расход вручную или через Apple Health.",
            ]
        )
    total = sum(activity.kcal for activity in activities)
    lines = ["🏃 Активность", "", f"За сегодня: {total:.0f} ккал", ""]
    for index, activity in enumerate(activities, start=1):
        lines.append(activity_line(index, activity, timezone_name))
    return "\n".join(lines)


def activity_line(index: int, activity, timezone_name: str) -> str:
    return (
        f"{index}. {entry_time_label(activity.created_at, timezone_name)} "
        f"{activity.activity_name} — {activity.kcal:.0f} ккал"
    )


def meal_summary_lines(entries, timezone_name: str) -> list[str]:
    lines: list[str] = []
    for label, meal_entries in entries_by_meal(entries, timezone_name):
        kcal = sum(entry.kcal for entry in meal_entries)
        count = len(meal_entries)
        suffix = f"{kcal:.0f} ккал" if count else "пока нет"
        if count:
            suffix += f" · {count}"
        lines.append(f"{label}: {suffix}")
    return lines


def entries_by_meal(entries, timezone_name: str):
    buckets = {
        "breakfast": [],
        "lunch": [],
        "dinner": [],
        "snacks": [],
    }
    for entry in entries:
        buckets[meal_key(entry.created_at, timezone_name)].append(entry)
    return [
        ("🌅 Завтрак", buckets["breakfast"]),
        ("☀️ Обед", buckets["lunch"]),
        ("🌙 Ужин", buckets["dinner"]),
        ("🍿 Перекусы", buckets["snacks"]),
    ]


def meal_key(created_at: datetime, timezone_name: str) -> str:
    hour = int(entry_time_label(created_at, timezone_name).split(":", 1)[0])
    if 5 <= hour < 12:
        return "breakfast"
    if 12 <= hour < 16:
        return "lunch"
    if 18 <= hour < 23:
        return "dinner"
    return "snacks"


def entry_time_label(created_at: datetime, timezone_name: str) -> str:
    tz = safe_timezone(timezone_name)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.astimezone(tz).strftime("%H:%M")


def macro_line(label: str, value: float, target: float) -> str:
    delta = target - value
    if delta >= 0:
        suffix = f"осталось {delta:.0f}г"
    else:
        suffix = f"перебор {abs(delta):.0f}г"
    return f"{label}: {value:.0f} / {target:.0f}г, {suffix}"


def parse_float(text: str, minimum: float, maximum: float) -> float | None:
    try:
        value = float(text.replace(",", ".").strip())
    except ValueError:
        return None
    return value if minimum <= value <= maximum else None


def parse_macros(text: str) -> tuple[float, float, float] | None:
    values = re.findall(r"\d+(?:[.,]\d+)?", text)
    if len(values) != 3:
        return None
    parsed = tuple(float(value.replace(",", ".")) for value in values)
    if any(value < 0 or value > 500 for value in parsed):
        return None
    return parsed


def parse_time(text: str) -> str | None:
    parts = text.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_favorite_payload(text: str) -> FoodEntryCreate | None:
    parts = [part.strip() for part in text.split(";")]
    if len(parts) != 6 or not parts[0]:
        return None
    try:
        weight_g = float(parts[1].replace(",", "."))
        kcal = float(parts[2].replace(",", "."))
        protein = float(parts[3].replace(",", "."))
        fat = float(parts[4].replace(",", "."))
        carbs = float(parts[5].replace(",", "."))
    except ValueError:
        return None
    if weight_g <= 0 or kcal < 0 or min(protein, fat, carbs) < 0:
        return None
    return FoodEntryCreate(
        name=parts[0],
        weight_g=weight_g,
        kcal=kcal,
        protein=protein,
        fat=fat,
        carbs=carbs,
        source="manual",
    )
