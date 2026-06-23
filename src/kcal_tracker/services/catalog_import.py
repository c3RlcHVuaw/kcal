from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import FoodCatalogAlias, FoodCatalogItem
from kcal_tracker.services.food_catalog import normalize_food_text


@dataclass(frozen=True)
class CatalogSeedRow:
    name: str
    aliases: tuple[str, ...]
    kcal: float
    protein: float
    fat: float
    carbs: float
    weight_g: float
    emoji: str | None
    advice: str | None
    source: str
    confidence: float
    trust_score: float


@dataclass(frozen=True)
class CatalogImportResult:
    created: int
    updated: int
    aliases_created: int
    skipped: int


def read_catalog_seed(path: str | Path) -> list[CatalogSeedRow]:
    rows: list[CatalogSeedRow] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for line_number, raw_row in enumerate(reader, start=2):
            row = _parse_seed_row(raw_row, line_number=line_number)
            if row is not None:
                rows.append(row)
    return rows


async def import_catalog_seed(
    session: AsyncSession,
    rows: list[CatalogSeedRow],
) -> CatalogImportResult:
    created = 0
    updated = 0
    aliases_created = 0
    skipped = 0

    for row in rows:
        normalized = normalize_food_text(row.name)
        if len(normalized) < 2:
            skipped += 1
            continue

        item = await session.scalar(
            select(FoodCatalogItem).where(
                FoodCatalogItem.user_id.is_(None),
                FoodCatalogItem.normalized_name == normalized,
            )
        )
        if item is None:
            item = FoodCatalogItem(
                user_id=None,
                food_name=row.name,
                normalized_name=normalized,
                kcal=row.kcal,
                protein=row.protein,
                fat=row.fat,
                carbs=row.carbs,
                weight_g=row.weight_g,
                emoji=row.emoji,
                advice=row.advice,
                source=row.source,
                confidence=row.confidence,
                trust_score=row.trust_score,
                usage_count=0,
                confirmed_count=1,
            )
            session.add(item)
            await session.flush()
            created += 1
        else:
            item.food_name = row.name
            item.kcal = row.kcal
            item.protein = row.protein
            item.fat = row.fat
            item.carbs = row.carbs
            item.weight_g = row.weight_g
            item.emoji = row.emoji or item.emoji
            item.advice = row.advice or item.advice
            item.source = row.source if item.source in {"curated", "seed"} else item.source
            item.confidence = max(item.confidence or 0, row.confidence)
            item.trust_score = max(item.trust_score, row.trust_score)
            item.confirmed_count = max(item.confirmed_count, 1)
            updated += 1

        for alias in (row.name, *row.aliases):
            aliases_created += await _ensure_alias(session, item, alias, row.source)

    await session.commit()
    return CatalogImportResult(
        created=created,
        updated=updated,
        aliases_created=aliases_created,
        skipped=skipped,
    )


def _parse_seed_row(raw_row: dict[str, str], *, line_number: int) -> CatalogSeedRow | None:
    name = (raw_row.get("name") or "").strip()
    if not name:
        return None
    try:
        weight_g = _positive_float(raw_row.get("weight_g"), "weight_g", line_number=line_number)
        kcal = _non_negative_float(raw_row.get("kcal"), "kcal", line_number=line_number)
        protein = _non_negative_float(raw_row.get("protein"), "protein", line_number=line_number)
        fat = _non_negative_float(raw_row.get("fat"), "fat", line_number=line_number)
        carbs = _non_negative_float(raw_row.get("carbs"), "carbs", line_number=line_number)
    except ValueError as exc:
        raise ValueError(f"Invalid catalog seed row {line_number}: {exc}") from exc

    aliases = tuple(
        alias.strip()
        for alias in (raw_row.get("aliases") or "").split("|")
        if alias.strip() and alias.strip() != name
    )
    source = (raw_row.get("source") or "seed").strip()[:32] or "seed"
    confidence = _bounded_float(raw_row.get("confidence"), default=0.88)
    trust_score = _bounded_float(raw_row.get("trust_score"), default=0.9)
    emoji = (raw_row.get("emoji") or "").strip() or None
    advice = (raw_row.get("advice") or "").strip()[:255] or None
    return CatalogSeedRow(
        name=name[:255],
        aliases=aliases[:20],
        kcal=kcal,
        protein=protein,
        fat=fat,
        carbs=carbs,
        weight_g=weight_g,
        emoji=emoji[:16] if emoji else None,
        advice=advice,
        source=source,
        confidence=confidence,
        trust_score=trust_score,
    )


async def _ensure_alias(
    session: AsyncSession,
    item: FoodCatalogItem,
    alias: str,
    source: str,
) -> int:
    normalized = normalize_food_text(alias)
    if len(normalized) < 2:
        return 0
    exists = await session.scalar(
        select(func.count(FoodCatalogAlias.id)).where(
            FoodCatalogAlias.item_id == item.id,
            FoodCatalogAlias.normalized_alias == normalized,
        )
    )
    if exists:
        return 0
    session.add(
        FoodCatalogAlias(
            item_id=item.id,
            alias=alias.strip()[:255],
            normalized_alias=normalized,
            source=source,
        )
    )
    return 1


def _positive_float(value: str | None, field: str, *, line_number: int) -> float:
    parsed = _non_negative_float(value, field, line_number=line_number)
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _non_negative_float(value: str | None, field: str, *, line_number: int) -> float:
    try:
        parsed = float((value or "").replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"{field} is not a number") from exc
    if parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return round(parsed, 2)


def _bounded_float(value: str | None, *, default: float) -> float:
    if not value:
        return default
    try:
        parsed = float(value.replace(",", "."))
    except ValueError:
        return default
    return min(1.0, max(0.0, parsed))
