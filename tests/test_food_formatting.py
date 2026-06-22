from __future__ import annotations

from kcal_tracker.bot.handlers.food_formatting import (
    extract_requested_grams,
    parse_positive_float,
    plural_ru,
)


def test_food_formatting_number_helpers() -> None:
    assert parse_positive_float("82,5") == 82.5
    assert parse_positive_float("-1") is None
    assert extract_requested_grams("творог 180 г") == 180
    assert extract_requested_grams("без граммовки") is None


def test_food_formatting_plural_ru() -> None:
    assert plural_ru(1, "позицию", "позиции", "позиций") == "позицию"
    assert plural_ru(3, "позицию", "позиции", "позиций") == "позиции"
    assert plural_ru(12, "позицию", "позиции", "позиций") == "позиций"
