from __future__ import annotations

from kcal_tracker.bot.handlers.food import (
    _filter_relevant_estimates,
    _is_confident_single_search_match,
)
from kcal_tracker.schemas import FoodEntryCreate, FoodEstimate
from kcal_tracker.services.food_catalog import _can_learn, normalize_food_text, scale_estimate
from kcal_tracker.services.food_search import estimate_common_food


def test_estimate_common_food_handles_milkshake_ocr_text() -> None:
    estimate = estimate_common_food(
        "КОКТЕЙЛЬ МОЛОЧНЫЙ ПАСТЕРИЗОВАННЫЙ СО ВКУСОМ ЛЕСНОГО ОРЕХА "
        "И КОФЕ ОРЕХОВЫЙ ЛАТТЕ"
    )

    assert estimate is not None
    assert estimate.name == "молочный коктейль"
    assert estimate.kcal == 85


def test_estimate_common_food_does_not_match_inside_words() -> None:
    assert estimate_common_food("ириска 50 г") is None
    assert estimate_common_food("сырники 150 г") is None


def test_food_search_filters_irrelevant_database_results() -> None:
    estimates = [
        FoodEstimate(name="картофельное пюре", kcal=120, confidence=0.75),
        FoodEstimate(name="ореховый латте", kcal=160, confidence=0.75),
    ]

    filtered = _filter_relevant_estimates("латте 300 мл", estimates, limit=5)

    assert [estimate.name for estimate in filtered] == ["ореховый латте"]


def test_single_database_result_needs_confident_match() -> None:
    estimate = FoodEstimate(name="ореховый латте", kcal=160, confidence=0.5)

    assert not _is_confident_single_search_match("латте 300 мл", estimate)
    assert _is_confident_single_search_match("латте", estimate)


def test_catalog_normalize_handles_case_and_yo() -> None:
    assert normalize_food_text("  ЁГУРТ, KFC!  ") == "егурт kfc"


def test_catalog_scales_estimate_preserving_metadata() -> None:
    estimate = FoodEstimate(
        name="наггетсы KFC",
        weight_g=100,
        kcal=270,
        protein=16,
        fat=17,
        carbs=15,
        source_label="Фастфуд",
        catalog_id=42,
        trust_score=0.9,
    )

    scaled = scale_estimate(estimate, 1.5)

    assert scaled.weight_g == 150
    assert scaled.kcal == 405
    assert scaled.protein == 24
    assert scaled.catalog_id == 42
    assert scaled.source_label == "Фастфуд"


def test_catalog_learning_rejects_low_confidence_payload() -> None:
    payload = FoodEntryCreate(
        name="пирожок",
        weight_g=100,
        kcal=240,
        protein=6,
        fat=8,
        carbs=35,
        confidence=0.4,
        source="manual",
    )

    assert not _can_learn(payload)
