from __future__ import annotations

import asyncio

from kcal_tracker.services.fatsecret import FatSecretService, _estimate_from_food


def test_fatsecret_estimate_uses_default_metric_serving_per_100g() -> None:
    estimate = _estimate_from_food(
        {
            "food_name": "Чизкейк",
            "brand_name": "Dodo Pizza",
            "servings": {
                "serving": [
                    {
                        "serving_description": "1 serving (125 g)",
                        "metric_serving_amount": "125",
                        "metric_serving_unit": "g",
                        "calories": "400",
                        "protein": "7.5",
                        "fat": "27.5",
                        "carbohydrate": "32.5",
                        "is_default": "1",
                    }
                ]
            },
        }
    )

    assert estimate is not None
    assert estimate.name == "Dodo Pizza Чизкейк"
    assert estimate.weight_g == 100
    assert estimate.kcal == 320
    assert estimate.protein == 6
    assert estimate.fat == 22
    assert estimate.carbs == 26


def test_fatsecret_search_returns_empty_without_credentials() -> None:
    service = FatSecretService()
    service.client_id = ""
    service.client_secret = ""

    result = asyncio.run(service.search_products("пицца"))

    assert result == []
