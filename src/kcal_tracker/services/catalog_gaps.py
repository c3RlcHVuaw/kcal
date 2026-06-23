from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import FoodCatalogAlias, FoodCatalogItem, QualityEvent
from kcal_tracker.services.food_catalog import normalize_food_text

PRODUCT_QUEUE_EVENT_TYPES = (
    "webapp_packaged_unverified",
    "webapp_ai_reject",
    "webapp_ai_adjust",
    "food_correction_learned",
    "food_no_match",
    "webapp_search_failed",
    "webapp_barcode_failed",
    "food_ai_failed",
    "webapp_ai_failed",
    "food_not_it",
)


@dataclass(frozen=True)
class CatalogGap:
    label: str
    normalized: str
    count: int
    score: int
    ready_count: int
    event_types: tuple[str, ...]
    sample_query: str | None
    product_add_command: str | None
    already_known: bool


async def catalog_gap_report(
    session: AsyncSession,
    *,
    days: int = 14,
    limit: int = 12,
) -> list[CatalogGap]:
    since = datetime.now(UTC) - timedelta(days=days)
    result = await session.execute(
        select(QualityEvent)
        .where(
            QualityEvent.created_at >= since,
            QualityEvent.event_type.in_(PRODUCT_QUEUE_EVENT_TYPES),
        )
        .order_by(QualityEvent.created_at.desc())
        .limit(500)
    )
    events = [
        event
        for event in result.scalars()
        if not isinstance(event.details, dict)
        or event.details.get("product_queue_status") != "ignored"
    ]
    gaps = summarize_catalog_gaps(events)
    known = await _known_normalized_foods(session, [gap.normalized for gap in gaps])
    ranked = [
        CatalogGap(
            label=gap.label,
            normalized=gap.normalized,
            count=gap.count,
            score=gap.score,
            ready_count=gap.ready_count,
            event_types=gap.event_types,
            sample_query=gap.sample_query,
            product_add_command=gap.product_add_command,
            already_known=gap.normalized in known,
        )
        for gap in gaps
    ]
    return sorted(ranked, key=lambda gap: (not gap.already_known, gap.score, gap.count), reverse=True)[
        :limit
    ]


def summarize_catalog_gaps(events: list[QualityEvent]) -> list[CatalogGap]:
    buckets: dict[str, dict[str, Any]] = {}
    for event in events:
        label = _gap_label(event)
        normalized = normalize_food_text(label)
        if len(normalized) < 2:
            continue
        bucket = buckets.setdefault(
            normalized,
            {
                "label": label,
                "count": 0,
                "score": 0,
                "ready_count": 0,
                "event_types": set(),
                "sample_query": None,
                "product_add_command": None,
            },
        )
        bucket["count"] += 1
        bucket["score"] += product_queue_weight(event)
        bucket["event_types"].add(event.event_type)
        if event.query and bucket["sample_query"] is None:
            bucket["sample_query"] = " ".join(str(event.query).split())[:160]
        command = product_add_command_for_event(event)
        if command:
            bucket["ready_count"] += 1
            bucket["product_add_command"] = bucket["product_add_command"] or command

    gaps = [
        CatalogGap(
            label=str(data["label"])[:120],
            normalized=normalized,
            count=int(data["count"]),
            score=int(data["score"]),
            ready_count=int(data["ready_count"]),
            event_types=tuple(sorted(data["event_types"])),
            sample_query=data["sample_query"],
            product_add_command=data["product_add_command"],
            already_known=False,
        )
        for normalized, data in buckets.items()
    ]
    return sorted(gaps, key=lambda gap: (gap.score, gap.count, gap.ready_count), reverse=True)


def product_queue_weight(event: QualityEvent) -> int:
    if event.event_type in {"webapp_packaged_unverified", "webapp_ai_reject", "food_not_it"}:
        return 40
    if event.event_type == "food_correction_learned":
        return 35
    if event.event_type in {"food_no_match", "webapp_search_failed", "webapp_barcode_failed"}:
        return 28
    if event.event_type in {"food_ai_failed", "webapp_ai_failed"}:
        return 16
    return 8


def product_add_command_for_event(event: QualityEvent) -> str | None:
    food = event_foods(event)[0] if event_foods(event) else None
    if food is None:
        return None
    name = _food_value(food, "name", event.query or "").strip()
    kcal = _num_value(food, "kcal")
    protein = _num_value(food, "protein")
    fat = _num_value(food, "fat")
    carbs = _num_value(food, "carbs")
    weight_g = _num_value(food, "weight_g")
    if not name or kcal <= 0 or weight_g <= 0:
        return None
    aliases = product_aliases_for_event(event, name)
    return (
        f"/product_add {name[:120]};{_fmt_num(kcal)};{_fmt_num(protein)};"
        f"{_fmt_num(fat)};{_fmt_num(carbs)};{_fmt_num(weight_g)};{aliases}"
    )


def product_aliases_for_event(event: QualityEvent, name: str) -> str:
    aliases = []
    query = " ".join(str(event.query or "").split())
    if query and normalize_food_text(query) != normalize_food_text(name):
        aliases.append(query[:80])
    aliases.extend(alias for alias in normalize_food_text(name).split()[:3] if len(alias) >= 3)
    deduped = []
    seen = set()
    for alias in aliases:
        normalized = normalize_food_text(alias)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(alias)
    return ", ".join(deduped[:5])


def event_foods(event: QualityEvent) -> list[dict]:
    details = event.details if isinstance(event.details, dict) else {}
    foods = details.get("foods")
    if isinstance(foods, list):
        return [food for food in foods if isinstance(food, dict)]
    return []


def _gap_label(event: QualityEvent) -> str:
    foods = event_foods(event)
    if foods:
        name = _food_value(foods[0], "name", "")
        if name:
            return name
    return " ".join(str(event.query or "").split())


async def _known_normalized_foods(session: AsyncSession, normalized_values: list[str]) -> set[str]:
    values = sorted({value for value in normalized_values if value})
    if not values:
        return set()
    items = await session.execute(
        select(FoodCatalogItem.normalized_name).where(
            FoodCatalogItem.user_id.is_(None),
            FoodCatalogItem.normalized_name.in_(values),
        )
    )
    aliases = await session.execute(
        select(FoodCatalogAlias.normalized_alias)
        .join(FoodCatalogItem, FoodCatalogAlias.item_id == FoodCatalogItem.id)
        .where(
            FoodCatalogItem.user_id.is_(None),
            FoodCatalogAlias.normalized_alias.in_(values),
        )
    )
    return set(items.scalars()) | set(aliases.scalars())


def _food_value(food: dict, key: str, default: str) -> str:
    value = food.get(key)
    return str(value).strip() if value not in (None, "") else default


def _num_value(food: dict, key: str) -> float:
    try:
        number = float(food.get(key) or 0)
    except (TypeError, ValueError):
        return 0
    return round(number, 1) if number > 0 else 0


def _fmt_num(value: float) -> str:
    return f"{round(value, 1):g}".replace(".", ",")
