from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import ProductCache
from kcal_tracker.schemas import FoodEstimate
from kcal_tracker.services.food_insights import enrich_food_payload


class ProductNotFoundError(RuntimeError):
    pass


class OpenFoodFactsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_product(self, barcode: str) -> ProductCache:
        cached = await self.session.get(ProductCache, barcode)
        if cached is not None:
            return cached

        url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                url,
                params={
                    "fields": (
                        "product_name_ru,product_name,product_name_en,"
                        "generic_name_ru,nutriments,quantity"
                    ),
                },
            )
            response.raise_for_status()
            payload = response.json()

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

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": query,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": 5,
                    "fields": (
                        "product_name_ru,product_name,product_name_en,"
                        "generic_name_ru,nutriments"
                    ),
                },
            )
            response.raise_for_status()
            payload = response.json()

        for product in payload.get("products") or []:
            estimate = _estimate_from_product(product)
            if estimate is not None:
                return estimate
        return None


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
