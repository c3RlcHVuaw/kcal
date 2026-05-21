from __future__ import annotations

import asyncio

from kcal_tracker.services.fatsecret import FatSecretService, _estimate_from_food, _query_variants


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


def test_fatsecret_estimate_parses_basic_food_description() -> None:
    estimate = _estimate_from_food(
        {
            "food_name": "Cheese Pizza",
            "food_description": (
                "Per 100g - Calories: 276kcal | Fat: 11.74g | "
                "Carbs: 30.33g | Protein: 12.33g"
            ),
        }
    )

    assert estimate is not None
    assert estimate.name == "Cheese Pizza"
    assert estimate.weight_g == 100
    assert estimate.kcal == 276
    assert estimate.protein == 12.3
    assert estimate.fat == 11.7
    assert estimate.carbs == 30.3


def test_fatsecret_query_variants_translate_common_russian_foods() -> None:
    assert _query_variants("чизкейк додо") == ["чизкейк додо", "cheesecake dodo", "cheesecake"]
    assert _query_variants("пицца") == ["пицца", "pizza"]


def test_fatsecret_search_returns_empty_without_credentials() -> None:
    service = FatSecretService()
    service.client_id = ""
    service.client_secret = ""

    result = asyncio.run(service.search_products("пицца"))

    assert result == []
