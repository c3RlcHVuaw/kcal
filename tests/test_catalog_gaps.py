from __future__ import annotations

from datetime import UTC, datetime

from kcal_tracker.models import QualityEvent
from kcal_tracker.services.catalog_gaps import (
    product_add_command_for_event,
    summarize_catalog_gaps,
)


def test_summarize_catalog_gaps_groups_by_normalized_food_name() -> None:
    events = [
        _event(
            "webapp_packaged_unverified",
            "Сырники 150 г",
            foods=[{"name": "Сырники", "kcal": 345, "protein": 18, "fat": 14, "carbs": 36, "weight_g": 150}],
        ),
        _event("food_no_match", "сырники"),
        _event("food_ai_failed", "гречка 200 г"),
    ]

    gaps = summarize_catalog_gaps(events)

    assert [gap.label for gap in gaps[:2]] == ["Сырники", "гречка 200 г"]
    assert gaps[0].count == 2
    assert gaps[0].score == 68
    assert gaps[0].ready_count == 1
    assert gaps[0].event_types == ("food_no_match", "webapp_packaged_unverified")
    assert gaps[0].product_add_command == "/product_add Сырники;345;18;14;36;150;Сырники 150 г, сырники"


def test_product_add_command_requires_calories_and_weight() -> None:
    event = _event(
        "webapp_packaged_unverified",
        "йогурт",
        foods=[{"name": "Йогурт", "kcal": 0, "protein": 4, "fat": 2, "carbs": 8, "weight_g": 125}],
    )

    assert product_add_command_for_event(event) is None


def _event(event_type: str, query: str, *, foods: list[dict] | None = None) -> QualityEvent:
    return QualityEvent(
        event_type=event_type,
        query=query,
        details={"foods": foods or []},
        created_at=datetime(2026, 6, 23, tzinfo=UTC),
    )
