from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from kcal_tracker.config import settings
from kcal_tracker.schemas import FoodEstimate
from kcal_tracker.services.food_insights import enrich_food_payload

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
SEARCH_URL = "https://platform.fatsecret.com/rest/foods/search/v3"
BASIC_SEARCH_URL = "https://platform.fatsecret.com/rest/server.api"

FOOD_QUERY_ALIASES = {
    "пицца": "pizza",
    "чизкейк": "cheesecake",
    "бургер": "burger",
    "гамбургер": "hamburger",
    "ролл": "roll",
    "суши": "sushi",
    "курица": "chicken",
    "говядина": "beef",
    "свинина": "pork",
    "лосось": "salmon",
    "рис": "rice",
    "гречка": "buckwheat",
    "овсянка": "oatmeal",
    "йогурт": "yogurt",
    "творог": "cottage cheese",
    "сыр": "cheese",
    "латте": "latte",
    "капучино": "cappuccino",
}

BRAND_QUERY_ALIASES = {
    "додо": "dodo",
    "вкусвилл": "vkusvill",
}


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float
    scope: str


_token_cache: dict[str, _TokenCache] = {}


class FatSecretService:
    def __init__(self) -> None:
        self.client_id = settings.fatsecret_client_id
        self.client_secret = settings.fatsecret_client_secret

    async def search_products(self, query: str, *, limit: int = 5) -> list[FoodEstimate]:
        query = " ".join(query.split())
        if len(query) < 2 or not self.client_id or not self.client_secret:
            return []

        try:
            token = await self._access_token(settings.fatsecret_scope)
        except FatSecretUnavailableError:
            try:
                token = await self._access_token("basic")
            except FatSecretUnavailableError:
                logger.debug("FatSecret token request failed", exc_info=True)
                return []

        async with httpx.AsyncClient(timeout=6.0) as client:
            for search_query in _query_variants(query):
                payload = await _premium_search(client, token, search_query, limit)
                if _has_api_error(payload):
                    basic_token = await self._access_token("basic")
                    payload = await _basic_search(client, basic_token, search_query, limit)
                estimates = _estimates_from_payload(payload)
                if estimates:
                    return estimates[:limit]
        return []

    async def _access_token(self, scope: str) -> str:
        now = time.time()
        cached = _token_cache.get(scope)
        if cached is not None and cached.expires_at > now + 30:
            return cached.access_token

        async with httpx.AsyncClient(timeout=6.0) as client:
            try:
                data = {"grant_type": "client_credentials"}
                if scope:
                    data["scope"] = scope
                response = await client.post(
                    TOKEN_URL,
                    data=data,
                    auth=(self.client_id, self.client_secret),
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise FatSecretUnavailableError("FatSecret token request failed") from exc

        access_token = payload.get("access_token")
        if not access_token:
            raise FatSecretUnavailableError("FatSecret token response has no access token")
        expires_in = _to_float(payload.get("expires_in")) or 3600
        _token_cache[scope] = _TokenCache(
            access_token=access_token,
            expires_at=now + expires_in,
            scope=scope,
        )
        return access_token


class FatSecretUnavailableError(RuntimeError):
    pass


def _estimate_from_food(food: dict[str, Any]) -> FoodEstimate | None:
    name = _food_name(food)
    if not name:
        return None

    description_estimate = _estimate_from_description(name, food.get("food_description"))
    if description_estimate is not None:
        return description_estimate

    serving = _best_serving(_as_list(food.get("servings", {}).get("serving")))
    if serving is None:
        return None

    calories = _to_float(serving.get("calories"))
    if calories is None:
        return None

    metric_amount = _to_float(serving.get("metric_serving_amount"))
    metric_unit = str(serving.get("metric_serving_unit") or "").lower()
    if metric_amount and metric_amount > 0 and metric_unit in {"g", "ml"}:
        ratio = 100 / metric_amount
        weight = 100.0
    else:
        ratio = 1.0
        weight = metric_amount if metric_amount and metric_unit == "g" else 100.0

    return enrich_food_payload(
        FoodEstimate(
            name=name,
            weight_g=weight,
            kcal=round(calories * ratio, 1),
            protein=round((_to_float(serving.get("protein")) or 0) * ratio, 1),
            fat=round((_to_float(serving.get("fat")) or 0) * ratio, 1),
            carbs=round((_to_float(serving.get("carbohydrate")) or 0) * ratio, 1),
            confidence=0.78,
        )
    )


def _food_name(food: dict[str, Any]) -> str:
    food_name = str(food.get("food_name") or "").strip()
    brand_name = str(food.get("brand_name") or "").strip()
    if brand_name and brand_name.casefold() not in food_name.casefold():
        return f"{brand_name} {food_name}"
    return food_name


async def _premium_search(
    client: httpx.AsyncClient,
    token: str,
    query: str,
    limit: int,
) -> dict[str, Any] | None:
    try:
        response = await client.get(
            SEARCH_URL,
            params={
                "search_expression": query,
                "max_results": min(max(limit, 1), 50),
                "format": "json",
                "region": settings.fatsecret_region,
                "language": settings.fatsecret_language,
                "flag_default_serving": "true",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        logger.debug("FatSecret premium search failed", exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


async def _basic_search(
    client: httpx.AsyncClient,
    token: str,
    query: str,
    limit: int,
) -> dict[str, Any] | None:
    try:
        response = await client.get(
            BASIC_SEARCH_URL,
            params={
                "method": "foods.search",
                "search_expression": query,
                "max_results": min(max(limit, 1), 50),
                "format": "json",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        logger.debug("FatSecret basic search failed", exc_info=True)
        return None
    return payload if isinstance(payload, dict) else None


def _foods_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    premium_foods = payload.get("foods_search", {}).get("results", {}).get("food")
    if premium_foods is not None:
        return _as_list(premium_foods)
    return _as_list(payload.get("foods", {}).get("food"))


def _estimates_from_payload(payload: dict[str, Any] | None) -> list[FoodEstimate]:
    if not payload:
        return []
    estimates = []
    for food in _foods_from_payload(payload):
        estimate = _estimate_from_food(food)
        if estimate is not None:
            estimates.append(estimate)
    return estimates


def _has_api_error(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return True
    return bool(payload.get("error"))


def _query_variants(query: str) -> list[str]:
    normalized = " ".join(query.casefold().replace("ё", "е").split())
    variants = [query]

    translated_tokens = []
    food_tokens = []
    for token in normalized.split():
        food_alias = FOOD_QUERY_ALIASES.get(token)
        brand_alias = BRAND_QUERY_ALIASES.get(token)
        if food_alias:
            translated_tokens.append(food_alias)
            food_tokens.append(food_alias)
        elif brand_alias:
            translated_tokens.append(brand_alias)
        else:
            translated_tokens.append(token)

    translated = " ".join(translated_tokens)
    food_only = " ".join(food_tokens)
    for variant in (translated, food_only):
        if variant and variant not in variants:
            variants.append(variant)
    return variants


def _estimate_from_description(name: str, description: Any) -> FoodEstimate | None:
    if not isinstance(description, str):
        return None
    per_match = re.search(r"per\s+100\s*g", description, flags=re.IGNORECASE)
    if not per_match:
        return None
    kcal = _extract_nutrient(description, "Calories", "kcal")
    fat = _extract_nutrient(description, "Fat", "g") or 0
    carbs = _extract_nutrient(description, "Carbs", "g") or 0
    protein = _extract_nutrient(description, "Protein", "g") or 0
    if kcal is None:
        return None
    return enrich_food_payload(
        FoodEstimate(
            name=name,
            weight_g=100,
            kcal=round(kcal, 1),
            protein=round(protein, 1),
            fat=round(fat, 1),
            carbs=round(carbs, 1),
            confidence=0.72,
        )
    )


def _extract_nutrient(description: str, label: str, unit: str) -> float | None:
    match = re.search(
        rf"{re.escape(label)}:\s*([0-9]+(?:[.,][0-9]+)?)\s*{re.escape(unit)}",
        description,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return _to_float(match.group(1).replace(",", "."))


def _best_serving(servings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not servings:
        return None
    for serving in servings:
        if str(serving.get("is_default")) == "1":
            return serving
    for serving in servings:
        amount = _to_float(serving.get("metric_serving_amount"))
        unit = str(serving.get("metric_serving_unit") or "").lower()
        if unit == "g" and amount and 95 <= amount <= 105:
            return serving
    return servings[0]


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
