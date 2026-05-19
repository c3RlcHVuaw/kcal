from datetime import UTC, datetime
from types import SimpleNamespace

from kcal_tracker.bot.handlers.diary import _entry_time_label
from kcal_tracker.bot.text_parsing import (
    looks_like_activity,
    parse_activity_kcal,
    parse_int_from_text,
)
from kcal_tracker.schemas import FoodEstimate
from kcal_tracker.services.ai_food import food_refinement_user_text, photo_recognition_user_text
from kcal_tracker.services.food_insights import enrich_food_payload, food_advice, food_emoji
from kcal_tracker.services.media import _sample_timestamps
from kcal_tracker.services.nutrition import high_calorie_add_warning, is_high_calorie_food


def test_confidence_must_be_less_than_one() -> None:
    estimate = FoodEstimate(name="Латте", kcal=120, confidence=0.99)
    assert estimate.confidence == 0.99


def test_food_insights_add_emoji_and_advice() -> None:
    estimate = enrich_food_payload(FoodEstimate(name="шоколадный торт", kcal=420, carbs=55))
    assert estimate.emoji == "🍫"
    assert estimate.advice is not None
    assert "сахара" in estimate.advice


def test_food_insights_detect_common_foods() -> None:
    assert food_emoji("гречка с курицей") == "🥣"
    assert "Белка" in food_advice("курица", kcal=220, protein=35, fat=6, carbs=0)


def test_high_calorie_warning_when_day_is_already_dense() -> None:
    summary = SimpleNamespace(
        kcal=1700,
        target_kcal=2000,
        entries=[
            SimpleNamespace(kcal=520, weight_g=180),
            SimpleNamespace(kcal=610, weight_g=220),
        ],
    )
    warning = high_calorie_add_warning(summary, FoodEstimate(name="пицца", kcal=550, weight_g=200))
    assert warning is not None
    assert "калорийные позиции" in warning


def test_high_calorie_warning_skips_light_foods() -> None:
    summary = SimpleNamespace(kcal=500, target_kcal=2000, entries=[])
    assert not is_high_calorie_food(FoodEstimate(name="салат", kcal=180, weight_g=250))
    assert high_calorie_add_warning(summary, FoodEstimate(name="салат", kcal=180)) is None


def test_photo_recognition_user_text_includes_caption_hint() -> None:
    text = photo_recognition_user_text("это половина порции, плюс 30 г соуса")
    assert "Уточнение пользователя" in text
    assert "половина порции" in text
    assert "30 г соуса" in text


def test_food_refinement_user_text_includes_current_estimate_and_hint() -> None:
    estimate = FoodEstimate(name="сырники", weight_g=160, kcal=330, protein=18)
    text = food_refinement_user_text(estimate, "ещё полито джемом")
    assert "Текущая оценка еды" in text
    assert "сырники" in text
    assert "ещё полито джемом" in text


def test_entry_time_label_uses_user_timezone_for_utc_timestamp() -> None:
    assert (
        _entry_time_label(datetime(2026, 5, 19, 7, 48, tzinfo=UTC), "Europe/Samara")
        == "11:48"
    )


def test_entry_time_label_treats_naive_timestamp_as_utc() -> None:
    assert _entry_time_label(datetime(2026, 5, 19, 7, 48), "Europe/Samara") == "11:48"


def test_parse_int_accepts_units() -> None:
    assert parse_int_from_text("250 мл", 1, 5000) == 250
    assert parse_int_from_text("добавить 500 миллилитров", 1, 5000) == 500


def test_parse_int_rejects_missing_or_out_of_range_value() -> None:
    assert parse_int_from_text("вода", 1, 5000) is None
    assert parse_int_from_text("7000 мл", 1, 5000) is None


def test_parse_activity_kcal_from_plain_text() -> None:
    assert looks_like_activity("я потратил 100 ккал")
    assert parse_activity_kcal("я потратил 100 ккал") == 100
    assert parse_activity_kcal("я съел 100 ккал") is None
    assert parse_activity_kcal("100 ккал", allow_plain_kcal=True) == 100


def test_sample_timestamps_cover_whole_video() -> None:
    assert _sample_timestamps(4.0, 5) == [0.0, 0.975, 1.95, 2.925, 3.9]
