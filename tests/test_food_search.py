from __future__ import annotations

from kcal_tracker.services.food_search import estimate_common_food


def test_estimate_common_food_handles_milkshake_ocr_text() -> None:
    estimate = estimate_common_food(
        "КОКТЕЙЛЬ МОЛОЧНЫЙ ПАСТЕРИЗОВАННЫЙ СО ВКУСОМ ЛЕСНОГО ОРЕХА "
        "И КОФЕ ОРЕХОВЫЙ ЛАТТЕ"
    )

    assert estimate is not None
    assert estimate.name == "молочный коктейль"
    assert estimate.kcal == 85
