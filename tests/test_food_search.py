from __future__ import annotations

from kcal_tracker.bot.handlers.food import (
    _filter_relevant_estimates,
    _is_confident_single_search_match,
)
from kcal_tracker.schemas import FoodEstimate
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
