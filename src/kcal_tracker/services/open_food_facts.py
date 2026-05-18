from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import ProductCache


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
