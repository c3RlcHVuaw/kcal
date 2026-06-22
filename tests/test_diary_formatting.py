from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from kcal_tracker.bot.handlers.diary_formatting import (
    entry_time_label,
    parse_favorite_payload,
    parse_float,
    parse_macros,
    parse_time,
)


def test_diary_formatting_parses_numbers_and_time() -> None:
    assert parse_float("82,5", 30, 250) == 82.5
    assert parse_float("12", 30, 250) is None
    assert parse_macros("30 20 100") == (30, 20, 100)
    assert parse_macros("30 20") is None
    assert parse_time("9:05") == "09:05"
    assert parse_time("25:00") is None


def test_diary_formatting_parses_favorite_payload() -> None:
    payload = parse_favorite_payload("Овсянка;250;320;12;8;50")

    assert payload is not None
    assert payload.name == "Овсянка"
    assert payload.weight_g == 250
    assert payload.source == "manual"


def test_diary_formatting_entry_time_uses_timezone() -> None:
    entry = SimpleNamespace(created_at=datetime(2026, 5, 19, 7, 48, tzinfo=UTC))

    assert entry_time_label(entry.created_at, "Europe/Samara") == "11:48"
