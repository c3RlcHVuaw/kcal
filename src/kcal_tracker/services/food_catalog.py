from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import FoodCatalogAlias, FoodCatalogItem, FoodEntry, User
from kcal_tracker.schemas import FoodEntryCreate, FoodEstimate
from kcal_tracker.services.food_insights import enrich_food_payload

MIN_LEARN_CONFIDENCE = 0.72


@dataclass(frozen=True)
class CuratedFood:
    name: str
    kcal: float
    protein: float
    fat: float
    carbs: float
    weight_g: float
    aliases: tuple[str, ...]
    emoji: str
    advice: str


CURATED_FAST_FOOD: tuple[CuratedFood, ...] = (
    CuratedFood(
        "наггетсы KFC / Rostic's",
        270,
        16,
        17,
        15,
        100,
        ("наггетсы кфс", "kfc nuggets", "ростикс наггетсы", "нагетсы кфс"),
        "🍗",
        "Фастфуд лучше добрать овощами или водой вместо сладкого напитка.",
    ),
    CuratedFood(
        "баскет дуэт KFC / Rostic's",
        950,
        48,
        58,
        58,
        390,
        ("баскет дуэт", "кфс баскет", "ростикс баскет", "баскет kfc"),
        "🍗",
        "Большая порция: удобно делить или учитывать как полноценный приём пищи.",
    ),
    CuratedFood(
        "Биг Мак",
        503,
        26,
        25,
        42,
        217,
        ("бигмак", "big mac", "мак биг мак", "макдональдс биг мак", "вкусно и точка биг мак"),
        "🍔",
        "К бургеру лучше добавить воду и не добирать день сладким напитком.",
    ),
    CuratedFood(
        "картофель фри",
        340,
        4,
        17,
        42,
        120,
        ("фри", "картошка фри", "картофель фри мак", "картофель фри кфс"),
        "🍟",
        "Фри быстро поднимает калории и соль, лучше брать маленькую порцию.",
    ),
    CuratedFood(
        "чизбургер",
        300,
        15,
        13,
        31,
        120,
        ("чизбургер мак", "cheeseburger", "мак чизбургер", "бургер чиз"),
        "🍔",
        "Норм как быстрый перекус, но белка обычно маловато для сытости.",
    ),
    CuratedFood(
        "воппер Burger King",
        640,
        29,
        35,
        52,
        290,
        ("воппер", "whopper", "бургер кинг воппер", "bk whopper"),
        "🍔",
        "Крупный бургер: учитывай соусы и гарнир отдельно, если добавляешь.",
    ),
    CuratedFood(
        "пепперони Dodo",
        250,
        11,
        11,
        27,
        100,
        ("додо пепперони", "пицца додо", "dodo pepperoni", "пепперони додо"),
        "🍕",
        "Пиццу удобнее считать по граммам или по доле круга.",
    ),
    CuratedFood(
        "саб с курицей Subway",
        460,
        28,
        12,
        60,
        230,
        ("subway курица", "сабвей курица", "саб с курицей", "сэндвич сабвей"),
        "🥪",
        "Соусы сильно меняют калории, лучше уточнять их отдельно.",
    ),
    CuratedFood(
        "бургер",
        260,
        13,
        12,
        25,
        100,
        ("гамбургер", "hamburger", "burger", "мак", "макдак"),
        "🍔",
        "Для точности выбери бренд или уточни вес/размер бургера.",
    ),
    CuratedFood(
        "ролл с курицей",
        210,
        12,
        8,
        22,
        100,
        ("твистер", "ролл кфс", "чикен ролл", "шаурма ролл"),
        "🌯",
        "Соус и сыр могут заметно увеличить жиры и калории.",
    ),
    CuratedFood(
        "соус",
        120,
        1,
        10,
        6,
        30,
        ("кетчуп", "сырный соус", "барбекю соус", "соус кфс", "соус мак"),
        "🥫",
        "Соусы маленькие по весу, но часто быстро добавляют калории.",
    ),
)


class FoodCatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, user: User, query: str, *, limit: int = 8) -> list[FoodEstimate]:
        await self.ensure_curated_seeded()
        normalized = normalize_food_text(query)
        if len(normalized) < 2:
            return []

        items: dict[int, tuple[FoodCatalogItem, float, str]] = {}
        for item, score, label in await self._matching_items(user, normalized):
            current = items.get(item.id)
            if current is None or score > current[1]:
                items[item.id] = (item, score, label)

        ranked = sorted(
            items.values(),
            key=lambda item: (item[1], item[0].trust_score, item[0].usage_count),
            reverse=True,
        )
        return [
            self._estimate_from_item(item, query=query, source_label=label)
            for item, _, label in ranked[:limit]
        ]

    async def learn_from_saved_entry(
        self,
        user: User,
        entry: FoodEntry,
        payload: FoodEntryCreate,
    ) -> None:
        if payload.catalog_id:
            await self.record_use(int(payload.catalog_id), confirmed=True)
            return

        if not _can_learn(payload):
            return

        normalized = normalize_food_text(payload.name)
        if len(normalized) < 3:
            return

        trust = min(0.82, max(0.45, (payload.confidence or MIN_LEARN_CONFIDENCE) - 0.08))
        item = await self._find_personal_item(user, normalized)
        if item is None:
            item = FoodCatalogItem(
                user_id=user.id,
                food_name=payload.name.strip(),
                normalized_name=normalized,
                kcal=round(entry.kcal, 1),
                protein=round(entry.protein, 1),
                fat=round(entry.fat, 1),
                carbs=round(entry.carbs, 1),
                weight_g=round(entry.weight_g, 1) if entry.weight_g is not None else None,
                emoji=entry.emoji,
                advice=entry.advice,
                source="ai_learned",
                confidence=payload.confidence,
                trust_score=trust,
                usage_count=1,
                confirmed_count=1,
            )
            self.session.add(item)
            await self.session.flush()
        else:
            item.kcal = round(entry.kcal, 1)
            item.protein = round(entry.protein, 1)
            item.fat = round(entry.fat, 1)
            item.carbs = round(entry.carbs, 1)
            item.weight_g = round(entry.weight_g, 1) if entry.weight_g is not None else None
            item.emoji = entry.emoji or item.emoji
            item.advice = entry.advice or item.advice
            item.confidence = max(item.confidence or 0, payload.confidence or 0)
            item.trust_score = min(0.9, max(item.trust_score, trust) + 0.04)
            item.usage_count += 1
            item.confirmed_count += 1

        await self._ensure_alias(item, payload.name, "ai")
        await self._maybe_promote_to_global(normalized)
        await self.session.commit()

    async def record_use(self, catalog_id: int, *, confirmed: bool = True) -> None:
        item = await self.session.get(FoodCatalogItem, catalog_id)
        if item is None:
            return
        item.usage_count += 1
        if confirmed:
            item.confirmed_count += 1
            item.trust_score = min(1.0, item.trust_score + 0.02)
        await self.session.commit()

    async def ensure_curated_seeded(self) -> None:
        existing = await self.session.scalar(
            select(func.count(FoodCatalogItem.id)).where(FoodCatalogItem.source == "curated")
        )
        if existing:
            return

        for food in CURATED_FAST_FOOD:
            item = FoodCatalogItem(
                user_id=None,
                food_name=food.name,
                normalized_name=normalize_food_text(food.name),
                kcal=food.kcal,
                protein=food.protein,
                fat=food.fat,
                carbs=food.carbs,
                weight_g=food.weight_g,
                emoji=food.emoji,
                advice=food.advice,
                source="curated",
                confidence=0.86,
                trust_score=0.92,
                usage_count=0,
                confirmed_count=0,
            )
            self.session.add(item)
            await self.session.flush()
            await self._ensure_alias(item, food.name, "curated")
            for alias in food.aliases:
                await self._ensure_alias(item, alias, "curated")
        await self.session.commit()

    async def _matching_items(
        self,
        user: User,
        normalized: str,
    ) -> list[tuple[FoodCatalogItem, float, str]]:
        patterns = _search_patterns(normalized)
        scope = or_(FoodCatalogItem.user_id.is_(None), FoodCatalogItem.user_id == user.id)
        item_result = await self.session.execute(
            select(FoodCatalogItem).where(
                scope,
                or_(*[FoodCatalogItem.normalized_name.ilike(pattern) for pattern in patterns]),
            )
        )
        matches = [
            (item, _score_text_match(normalized, item.normalized_name, item), _source_label(item))
            for item in item_result.scalars()
        ]

        alias_result = await self.session.execute(
            select(FoodCatalogAlias, FoodCatalogItem)
            .join(FoodCatalogItem, FoodCatalogAlias.item_id == FoodCatalogItem.id)
            .where(
                scope,
                or_(*[FoodCatalogAlias.normalized_alias.ilike(pattern) for pattern in patterns]),
            )
        )
        for alias, item in alias_result.all():
            score = _score_text_match(normalized, alias.normalized_alias, item) + 0.18
            matches.append((item, score, _source_label(item)))
        return [match for match in matches if match[1] >= 0.32]

    async def _find_personal_item(self, user: User, normalized: str) -> FoodCatalogItem | None:
        result = await self.session.execute(
            select(FoodCatalogItem).where(
                FoodCatalogItem.user_id == user.id,
                FoodCatalogItem.normalized_name == normalized,
            )
        )
        exact = result.scalar_one_or_none()
        if exact is not None:
            return exact

        tokens = normalized.split()
        if not tokens:
            return None
        candidates = await self.session.execute(
            select(FoodCatalogItem).where(
                FoodCatalogItem.user_id == user.id,
                or_(*[FoodCatalogItem.normalized_name.ilike(f"%{token}%") for token in tokens[:4]]),
            )
        )
        best: FoodCatalogItem | None = None
        best_score = 0.0
        for item in candidates.scalars():
            score = _dedup_similarity(normalized, item.normalized_name)
            if score > best_score:
                best = item
                best_score = score
        return best if best is not None and best_score >= 0.86 else None

    async def _ensure_alias(self, item: FoodCatalogItem, alias: str, source: str) -> None:
        normalized = normalize_food_text(alias)
        if len(normalized) < 2:
            return
        exists = await self.session.scalar(
            select(func.count(FoodCatalogAlias.id)).where(
                FoodCatalogAlias.item_id == item.id,
                FoodCatalogAlias.normalized_alias == normalized,
            )
        )
        if exists:
            return
        self.session.add(
            FoodCatalogAlias(
                item_id=item.id,
                alias=alias.strip()[:255],
                normalized_alias=normalized,
                source=source,
            )
        )

    async def _maybe_promote_to_global(self, normalized: str) -> None:
        global_item = await self.session.scalar(
            select(FoodCatalogItem).where(
                FoodCatalogItem.user_id.is_(None),
                FoodCatalogItem.normalized_name == normalized,
            )
        )
        if global_item is not None:
            global_item.confirmed_count += 1
            global_item.trust_score = min(0.95, global_item.trust_score + 0.03)
            return

        personal_result = await self.session.execute(
            select(FoodCatalogItem).where(
                FoodCatalogItem.user_id.is_not(None),
                FoodCatalogItem.normalized_name == normalized,
                FoodCatalogItem.confirmed_count >= 1,
            )
        )
        personal_items = list(personal_result.scalars())
        distinct_users = {item.user_id for item in personal_items}
        if len(distinct_users) < 2:
            return

        base = max(personal_items, key=lambda item: (item.trust_score, item.confirmed_count))
        promoted = FoodCatalogItem(
            user_id=None,
            food_name=base.food_name,
            normalized_name=base.normalized_name,
            kcal=base.kcal,
            protein=base.protein,
            fat=base.fat,
            carbs=base.carbs,
            weight_g=base.weight_g,
            emoji=base.emoji,
            advice=base.advice,
            source="ai_learned",
            confidence=base.confidence,
            trust_score=min(0.84, base.trust_score + 0.06),
            usage_count=sum(item.usage_count for item in personal_items),
            confirmed_count=sum(item.confirmed_count for item in personal_items),
        )
        self.session.add(promoted)
        await self.session.flush()
        await self._ensure_alias(promoted, promoted.food_name, "ai")

    def _estimate_from_item(
        self,
        item: FoodCatalogItem,
        *,
        query: str,
        source_label: str,
    ) -> FoodEstimate:
        estimate = FoodEstimate(
            name=item.food_name,
            weight_g=item.weight_g,
            kcal=item.kcal,
            protein=item.protein,
            fat=item.fat,
            carbs=item.carbs,
            confidence=item.confidence,
            emoji=item.emoji,
            advice=item.advice,
            source_label=source_label,
            catalog_id=item.id,
            trust_score=item.trust_score,
        )
        grams = extract_requested_grams(query)
        if grams is not None and estimate.weight_g:
            estimate = scale_estimate(estimate, grams / estimate.weight_g)
            estimate.catalog_id = item.id
            estimate.source_label = source_label
            estimate.trust_score = item.trust_score
        return enrich_food_payload(estimate)


def normalize_food_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    value = re.sub(r"[^0-9a-zа-я]+", " ", value)
    return " ".join(value.split())[:255]


def extract_requested_grams(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:г|гр|грамм|g)\b", text.casefold())
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    if 0 < value <= 5000:
        return value
    return None


def scale_estimate(estimate: FoodEstimate, scale: float) -> FoodEstimate:
    return enrich_food_payload(
        FoodEstimate(
            name=estimate.name,
            weight_g=round((estimate.weight_g or 0) * scale, 1) if estimate.weight_g else None,
            kcal=round(estimate.kcal * scale, 1),
            protein=round(estimate.protein * scale, 1),
            fat=round(estimate.fat * scale, 1),
            carbs=round(estimate.carbs * scale, 1),
            confidence=estimate.confidence,
            emoji=estimate.emoji,
            advice=estimate.advice,
            source_label=estimate.source_label,
            catalog_id=estimate.catalog_id,
            is_ai_suggestion=estimate.is_ai_suggestion,
            trust_score=estimate.trust_score,
        )
    )


def mark_ai_suggestions(estimates: list[FoodEstimate]) -> list[FoodEstimate]:
    marked = []
    for estimate in estimates:
        estimate.is_ai_suggestion = True
        estimate.source_label = "AI"
        estimate.trust_score = estimate.confidence
        marked.append(enrich_food_payload(estimate))
    return marked


def _search_patterns(normalized: str) -> list[str]:
    tokens = normalized.split()
    patterns = [f"%{normalized}%"]
    if len(tokens) > 1:
        patterns.extend(f"%{token}%" for token in tokens if len(token) >= 3)
    return patterns[:5]


def _score_text_match(query: str, candidate: str, item: FoodCatalogItem) -> float:
    if query == candidate:
        score = 1.0
    elif query in candidate or candidate in query:
        score = 0.82
    else:
        query_tokens = set(query.split())
        candidate_tokens = set(candidate.split())
        overlap = len(query_tokens & candidate_tokens)
        score = overlap / max(len(query_tokens), 1)
    if item.user_id is not None:
        score += 0.12
    if item.source == "curated":
        score += 0.1
    score += min(item.trust_score, 1.0) * 0.18
    score += min(item.usage_count, 20) * 0.005
    return score


def _dedup_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    token_score = (2 * overlap) / (len(left_tokens) + len(right_tokens))
    substring_score = 0.88 if left in right or right in left else 0.0
    return max(token_score, substring_score)


def _source_label(item: FoodCatalogItem) -> str:
    if item.user_id is not None:
        return "История"
    if item.source == "admin":
        return "Проверено"
    if item.source == "curated":
        return "Фастфуд"
    if item.source == "ai_learned":
        return "База"
    return "База"


def _can_learn(payload: FoodEntryCreate) -> bool:
    if (payload.confidence or 0) < MIN_LEARN_CONFIDENCE:
        return False
    if not payload.weight_g or payload.weight_g <= 0 or payload.kcal <= 0:
        return False
    if payload.protein + payload.fat + payload.carbs <= 0:
        return False
    if payload.kcal > 3000 or payload.weight_g > 5000:
        return False
    if payload.source not in {"manual", "ai_photo", "food_search", "history"}:
        return False
    return bool(payload.is_ai_suggestion or payload.source in {"manual", "ai_photo"})
