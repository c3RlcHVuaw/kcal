from __future__ import annotations

import logging
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


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float


_token_cache: _TokenCache | None = None


class FatSecretService:
    def __init__(self) -> None:
        self.client_id = settings.fatsecret_client_id
        self.client_secret = settings.fatsecret_client_secret

    async def search_products(self, query: str, *, limit: int = 5) -> list[FoodEstimate]:
        query = " ".join(query.split())
        if len(query) < 2 or not self.client_id or not self.client_secret:
            return []

        try:
            token = await self._access_token()
        except FatSecretUnavailableError:
            logger.debug("FatSecret token request failed", exc_info=True)
            return []

        async with httpx.AsyncClient(timeout=6.0) as client:
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
                logger.debug("FatSecret search failed", exc_info=True)
                return []

        foods = _as_list(payload.get("foods_search", {}).get("results", {}).get("food"))
        estimates = []
        for food in foods:
            estimate = _estimate_from_food(food)
            if estimate is not None:
                estimates.append(estimate)
        return estimates[:limit]

    async def _access_token(self) -> str:
        global _token_cache
        now = time.time()
        if _token_cache is not None and _token_cache.expires_at > now + 30:
            return _token_cache.access_token

        async with httpx.AsyncClient(timeout=6.0) as client:
            try:
                response = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "scope": settings.fatsecret_scope,
                    },
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
        _token_cache = _TokenCache(access_token=access_token, expires_at=now + expires_in)
        return access_token


class FatSecretUnavailableError(RuntimeError):
    pass


def _estimate_from_food(food: dict[str, Any]) -> FoodEstimate | None:
    name = _food_name(food)
    if not name:
        return None

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
