from __future__ import annotations

import asyncio
import logging
import re
import unicodedata

from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.config import settings
from kcal_tracker.schemas import FoodEstimate, FoodEstimateList
from kcal_tracker.services.fatsecret import FatSecretService
from kcal_tracker.services.open_food_facts import OpenFoodFactsService

BRAND_LOOKUP_MIN_SCORE = 0.55
UNVERIFIED_PACKAGED_LABEL = "Проверь бренд"
UNVERIFIED_PACKAGED_ADVICE = (
    "Не нашёл точное совпадение упаковки в базе. Проверь бренд, вкус и КБЖУ перед сохранением."
)
BRAND_HINT_TOKENS = {
    "activia",
    "alpen",
    "bombbar",
    "coca",
    "danone",
    "dodo",
    "epica",
    "kfc",
    "lays",
    "mars",
    "milka",
    "nestle",
    "oreo",
    "pepsi",
    "pringles",
    "ritter",
    "snickers",
    "subway",
    "twix",
    "vkusvill",
    "активиа",
    "вкусвилл",
    "додо",
    "простоквашино",
    "чудо",
}
logger = logging.getLogger(__name__)


async def match_photo_estimates_to_brands(
    session: AsyncSession,
    estimates: FoodEstimateList,
    *,
    limit: int = 8,
) -> FoodEstimateList:
    if not estimates.foods:
        return estimates

    matched: list[FoodEstimate] = []
    for estimate in estimates.foods[:limit]:
        brand_match = await match_photo_estimate_to_brand(session, estimate)
        matched.append(brand_match or mark_unverified_packaged_estimate(estimate))
    return FoodEstimateList(foods=matched)


async def match_photo_estimate_to_brand(
    session: AsyncSession,
    estimate: FoodEstimate,
) -> FoodEstimate | None:
    if not _looks_like_packaged_estimate(estimate):
        return None

    candidates: list[FoodEstimate] = []
    queries = _brand_lookup_queries(estimate)
    try:
        for query in queries:
            candidates.extend(
                await asyncio.wait_for(
                    OpenFoodFactsService(session).search_products(query, limit=5),
                    timeout=settings.food_search_openfoodfacts_timeout_seconds,
                )
            )
            if len(candidates) >= 5:
                break
    except TimeoutError:
        candidates = []
    except Exception:
        logger.debug("OpenFoodFacts brand lookup failed", exc_info=True)
        candidates = []

    if len(candidates) < 3:
        try:
            for query in queries:
                candidates.extend(
                    await asyncio.wait_for(
                        FatSecretService().search_products(query, limit=5),
                        timeout=settings.food_search_fatsecret_timeout_seconds,
                    )
                )
                if len(candidates) >= 5:
                    break
        except TimeoutError:
            pass
        except Exception:
            logger.debug("FatSecret brand lookup failed", exc_info=True)
            pass

    best = _best_brand_match(estimate, candidates)
    if best is None:
        return None
    best.confidence = max(best.confidence or 0, 0.82)
    best.source_label = "База бренда"
    best.is_ai_suggestion = False
    best.packaged = True
    best.visible_brand = estimate.visible_brand
    best.visible_label_text = estimate.visible_label_text
    best.photo_thumb_data_url = estimate.photo_thumb_data_url
    best.photo_thumb_expires_at = estimate.photo_thumb_expires_at
    return best


def _best_brand_match(estimate: FoodEstimate, candidates: list[FoodEstimate]) -> FoodEstimate | None:
    best: FoodEstimate | None = None
    best_score = 0.0
    query_tokens = set(_brand_query_tokens(estimate))
    for candidate in candidates:
        score = _name_similarity(estimate.name, candidate.name)
        candidate_tokens = set(_meaningful_tokens(candidate.name))
        if query_tokens and candidate_tokens:
            token_score = (2 * len(query_tokens & candidate_tokens)) / (
                len(query_tokens) + len(candidate_tokens)
            )
            score = max(score, token_score)
        if score > best_score:
            best = candidate
            best_score = score
    return best if best is not None and best_score >= BRAND_LOOKUP_MIN_SCORE else None


def mark_unverified_packaged_estimate(estimate: FoodEstimate) -> FoodEstimate:
    if not _looks_like_packaged_estimate(estimate):
        return estimate
    estimate.confidence = min(estimate.confidence or 0.55, 0.55)
    estimate.source_label = UNVERIFIED_PACKAGED_LABEL
    estimate.is_ai_suggestion = True
    estimate.packaged = True
    if not estimate.advice or "точное совпадение упаковки" not in estimate.advice:
        estimate.advice = UNVERIFIED_PACKAGED_ADVICE
    return estimate


def _brand_lookup_queries(estimate: FoodEstimate) -> list[str]:
    values = [
        estimate.visible_label_text,
        " ".join(value for value in [estimate.visible_brand, estimate.name] if value),
        estimate.name,
    ]
    queries: list[str] = []
    for value in values:
        if not value:
            continue
        cleaned = " ".join(value.split())
        if len(cleaned) >= 2 and cleaned not in queries:
            queries.append(cleaned)
    return queries or [estimate.name]


def _brand_query_tokens(estimate: FoodEstimate) -> list[str]:
    return _meaningful_tokens(
        " ".join(
            value
            for value in [estimate.visible_brand, estimate.visible_label_text, estimate.name]
            if value
        )
    )


def _name_similarity(left: str, right: str) -> float:
    left_tokens = set(_meaningful_tokens(left))
    right_tokens = set(_meaningful_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    return (2 * len(overlap)) / (len(left_tokens) + len(right_tokens))


def _looks_like_packaged_estimate(estimate: FoodEstimate) -> bool:
    if estimate.packaged is True:
        return True
    if estimate.visible_brand or estimate.visible_label_text:
        return True
    normalized = unicodedata.normalize("NFKC", estimate.name).casefold().replace("ё", "е")
    if re.search(r"[a-z]{3,}", normalized):
        return True
    if re.search(r"\d", normalized):
        return True
    tokens = set(_meaningful_tokens(estimate.name))
    return bool(tokens & BRAND_HINT_TOKENS)


def _meaningful_tokens(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    tokens = re.findall(r"[0-9a-zа-я]{3,}", value)
    stop_words = {
        "продукт",
        "еда",
        "упаковка",
        "пачка",
        "порция",
        "батончик",
        "напиток",
        "йогурт",
        "молоко",
        "сыр",
        "печенье",
        "шоколад",
        "вкус",
        "без",
    }
    return [token for token in tokens if token not in stop_words]
