from __future__ import annotations

import re
import unicodedata

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import ProductCache
from kcal_tracker.schemas import FoodEstimate
from kcal_tracker.services.food_insights import enrich_food_payload


class ProductNotFoundError(RuntimeError):
    pass


OPEN_FOOD_FACTS_HEADERS = {
    "User-Agent": "KcalTrackerBot/0.1 (+https://t.me/trackerkcal_bot)",
    "Accept": "application/json",
}

SEARCH_ENDPOINTS = (
    "https://ru.openfoodfacts.org/api/v2/search",
    "https://world.openfoodfacts.org/api/v2/search",
    "https://ru.openfoodfacts.org/cgi/search.pl",
    "https://world.openfoodfacts.org/cgi/search.pl",
)

PRODUCT_ENDPOINTS = (
    "https://ru.openfoodfacts.org/api/v2/product/{barcode}.json",
    "https://world.openfoodfacts.org/api/v2/product/{barcode}.json",
)


class OpenFoodFactsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_product(self, barcode: str) -> ProductCache:
        cached = await self.session.get(ProductCache, barcode)
        if cached is not None:
            return cached

        async with httpx.AsyncClient(timeout=4.0) as client:
            payload = None
            for url_template in PRODUCT_ENDPOINTS:
                try:
                    response = await client.get(
                        url_template.format(barcode=barcode),
                        params={
                            "fields": (
                                "product_name_ru,product_name,product_name_en,"
                                "generic_name_ru,nutriments,quantity"
                            ),
                        },
                        headers=OPEN_FOOD_FACTS_HEADERS,
                    )
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("status") == 1:
                        break
                except (httpx.HTTPError, ValueError):
                    continue
            if payload is None:
                raise ProductNotFoundError("OpenFoodFacts is unavailable")

        if payload.get("status") != 1:
            raise ProductNotFoundError("Product not found")

        product = payload["product"]
        nutriments = product.get("nutriments") or {}
        product_name = (
            product.get("product_name_ru")
            or product.get("generic_name_ru")
            or product.get("product_name")
            or product.get("product_name_en")
            or "Продукт по штрихкоду"
        )
        cache = ProductCache(
            barcode=barcode,
            product_name=product_name,
            kcal_100g=nutriments.get("energy-kcal_100g"),
            protein_100g=nutriments.get("proteins_100g"),
            fat_100g=nutriments.get("fat_100g"),
            carbs_100g=nutriments.get("carbohydrates_100g"),
            raw_json=payload,
        )
        self.session.add(cache)
        await self.session.commit()
        await self.session.refresh(cache)
        return cache

    async def search_product(self, query: str) -> FoodEstimate | None:
        query = " ".join(query.split())
        if len(query) < 2:
            return None

        query_variants = _search_queries(query)
        async with httpx.AsyncClient(timeout=5.0) as client:
            for search_query in query_variants:
                for base_url in SEARCH_ENDPOINTS:
                    payload = await _search_payload(client, base_url, search_query)
                    if payload is None:
                        continue
                    for product in payload.get("products") or []:
                        if not _is_relevant_product(product, search_query):
                            continue
                        estimate = _estimate_from_product(product)
                        if estimate is not None:
                            return estimate
        return None


async def _search_payload(
    client: httpx.AsyncClient,
    base_url: str,
    query: str,
) -> dict | None:
    try:
        response = await client.get(
            base_url,
            params={
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 10,
                "sort_by": "popularity_key",
                "fields": (
                    "product_name_ru,product_name,product_name_en,"
                    "generic_name_ru,nutriments"
                ),
            },
            headers=OPEN_FOOD_FACTS_HEADERS,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _estimate_from_product(product: dict) -> FoodEstimate | None:
    nutriments = product.get("nutriments") or {}
    kcal = nutriments.get("energy-kcal_100g")
    if kcal is None:
        return None
    name = (
        product.get("product_name_ru")
        or product.get("generic_name_ru")
        or product.get("product_name")
        or product.get("product_name_en")
    )
    if not name:
        return None
    return enrich_food_payload(
        FoodEstimate(
            name=name,
            weight_g=100,
            kcal=kcal,
            protein=nutriments.get("proteins_100g") or 0,
            fat=nutriments.get("fat_100g") or 0,
            carbs=nutriments.get("carbohydrates_100g") or 0,
            confidence=0.7,
        )
    )


def _search_queries(query: str) -> list[str]:
    normalized = _normalize_search_text(query)
    variants: list[str] = []

    quoted = re.findall(r"[«\"]([^»\"]{3,})[»\"]", query)
    for value in quoted:
        variants.append(_normalize_search_text(value))

    variants.append(normalized)

    compact = _drop_ocr_noise(normalized)
    if compact != normalized:
        variants.append(compact)

    tokens = compact.split()
    if len(tokens) > 6:
        variants.append(" ".join(tokens[:6]))
        variants.append(" ".join(tokens[-5:]))
    if len(tokens) > 3:
        variants.append(" ".join(tokens[-3:]))

    deduped: list[str] = []
    for variant in variants:
        variant = " ".join(variant.split())
        if len(variant) >= 2 and variant not in deduped:
            deduped.append(variant)
    return deduped[:6]


def _normalize_search_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"\((?:rus|eng|ru|en)\)", " ", value, flags=re.IGNORECASE)
    value = value.replace("ё", "е")
    value = re.sub(r"[^0-9a-zа-я]+", " ", value)
    return " ".join(value.split())


def _drop_ocr_noise(value: str) -> str:
    stop_words = {
        "пастеризованный",
        "пастеризованныи",
        "обогащенный",
        "обогащенныи",
        "молочным",
        "белком",
        "белок",
        "вкусом",
        "вкуса",
        "со",
        "и",
        "лесного",
        "ореха",
    }
    tokens = [token for token in value.split() if token not in stop_words]
    return " ".join(tokens)


def _is_relevant_product(product: dict, query: str) -> bool:
    name = _product_name(product)
    if not name:
        return False
    query_tokens = _meaningful_tokens(query)
    if not query_tokens:
        return True
    name_tokens = set(_meaningful_tokens(name))
    matches = sum(1 for token in query_tokens if token in name_tokens)
    if len(query_tokens) <= 2:
        return matches == len(query_tokens)
    return matches >= 2


def _meaningful_tokens(value: str) -> list[str]:
    tokens = _normalize_search_text(value).split()
    return [token for token in tokens if len(token) > 2]


def _product_name(product: dict) -> str:
    return (
        product.get("product_name_ru")
        or product.get("generic_name_ru")
        or product.get("product_name")
        or product.get("product_name_en")
        or ""
    )
