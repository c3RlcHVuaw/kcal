from kcal_tracker.bot.text_parsing import (
    looks_like_activity,
    parse_activity_kcal,
    parse_int_from_text,
)
from kcal_tracker.schemas import FoodEstimate
from kcal_tracker.services.media import _sample_timestamps


def test_confidence_must_be_less_than_one() -> None:
    estimate = FoodEstimate(name="Латте", kcal=120, confidence=0.99)
    assert estimate.confidence == 0.99


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
