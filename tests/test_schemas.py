from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from kcal_tracker.api.routes import (
    _extract_numeric_total,
    _extract_numeric_value,
    _normalize_apple_health_payload,
    _steps_to_kcal,
)
from kcal_tracker.bot.handlers.diary import (
    ADVANCED_PATTERNS_UPSELL,
    _entries_by_meal,
    _entry_line,
    _entry_time_label,
    _habit_lines,
    _meal_summary_lines,
    _month_delta_line,
    _month_focus,
    _today_view,
    _week_highlight_lines,
    _weight_chart,
)
from kcal_tracker.bot.handlers.food import _format_estimate_confirmation, _scale_estimate
from kcal_tracker.bot.handlers.profile import _apple_health_shortcut_text
from kcal_tracker.bot.keyboards import (
    food_confirmation_keyboard,
    food_entries_keyboard,
    settings_keyboard,
)
from kcal_tracker.bot.text_parsing import (
    looks_like_activity,
    parse_activity_kcal,
    parse_int_from_text,
)
from kcal_tracker.schemas import FoodEstimate
from kcal_tracker.services.ai_food import food_refinement_user_text, photo_recognition_user_text
from kcal_tracker.services.diary import NutritionPatterns, estimate_from_entry
from kcal_tracker.services.food_insights import enrich_food_payload, food_advice, food_emoji
from kcal_tracker.services.media import _sample_timestamps
from kcal_tracker.services.nutrition import (
    automatic_pattern_notes,
    daily_focus,
    end_of_day_forecast,
    high_calorie_add_warning,
    is_high_calorie_food,
    meal_suggestion_text,
    smart_day_coach,
    smart_problem_signals,
    weekly_coach_note,
    weekly_score,
)
from kcal_tracker.services.reminders import (
    _has_meal_entry,
    _inactivity_reminder_due,
    _inactivity_reminder_text,
)


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


def test_smart_day_coach_focuses_on_missing_protein() -> None:
    summary = SimpleNamespace(
        kcal=1300,
        target_kcal=2000,
        protein=45,
        target_protein=120,
        fat=45,
        target_fat=70,
        carbs=170,
        target_carbs=230,
        entries=[SimpleNamespace()],
    )
    assert "белка" in smart_day_coach(summary)
    assert daily_focus(summary) == "добрать белок"


def test_meal_suggestion_prefers_light_food_when_calories_are_spent() -> None:
    summary = SimpleNamespace(
        kcal=2050,
        target_kcal=2100,
        protein=100,
        target_protein=110,
        fat=70,
        target_fat=70,
        carbs=220,
        target_carbs=230,
        entries=[SimpleNamespace()],
    )
    text = meal_suggestion_text(summary, water_ml=500)
    assert "Калорий почти не осталось" in text
    assert "стакан воды" in text


def test_weekly_coach_note_mentions_average_delta() -> None:
    analytics = SimpleNamespace(
        average_kcal=2300,
        target_kcal=2000,
        days_in_target=1,
        days=[
            SimpleNamespace(entries_count=2, protein=70, fat=95, carbs=250),
            SimpleNamespace(entries_count=3, protein=75, fat=100, carbs=260),
            SimpleNamespace(entries_count=0, protein=0, fat=0, carbs=0),
        ],
    )
    note = weekly_coach_note(analytics)
    assert "AI-разбор недели" in note
    assert "перебор" in note
    assert weekly_score(analytics) >= 1


def test_end_of_day_forecast_uses_usual_evening_kcal() -> None:
    summary = SimpleNamespace(
        kcal=1750,
        target_kcal=2100,
        entries=[SimpleNamespace()],
    )
    patterns = NutritionPatterns(
        tracked_days=8,
        average_evening_kcal=650,
        no_breakfast_days=0,
        no_breakfast_over_target_days=0,
        sweet_drink_days=0,
        sweet_drink_average_delta=0,
    )
    forecast = end_of_day_forecast(summary, patterns)
    assert forecast is not None
    assert "плюс примерно на 300 ккал" in forecast


def test_automatic_pattern_notes_detect_no_breakfast_and_sweet_drinks() -> None:
    patterns = NutritionPatterns(
        tracked_days=10,
        average_evening_kcal=620,
        no_breakfast_days=4,
        no_breakfast_over_target_days=3,
        sweet_drink_days=3,
        sweet_drink_average_delta=210,
    )
    notes = automatic_pattern_notes(patterns)
    assert any("без завтрака" in note for note in notes)
    assert any("сладкими напитками" in note for note in notes)


def test_today_view_hides_advanced_patterns_without_subscription() -> None:
    summary = SimpleNamespace(
        kcal=900,
        target_kcal=2000,
        activity_kcal=0,
        protein=45,
        target_protein=120,
        fat=30,
        target_fat=70,
        carbs=110,
        target_carbs=230,
        entries=[],
    )
    text, _ = _today_view(summary, 800, patterns=None, include_advice=True)
    assert ADVANCED_PATTERNS_UPSELL in text
    assert "✨ AI-совет дня\n\n✅" in text
    assert "🎯 Фокус:" in text
    assert "🔒 " + ADVANCED_PATTERNS_UPSELL in text
    assert "Паттерны: пока мало истории" not in text


def test_today_entry_line_is_compact_and_hides_item_advice() -> None:
    entry = SimpleNamespace(
        created_at=datetime(2026, 5, 19, 7, 20, tzinfo=UTC),
        food_name="бутерброд из гриля",
        weight_g=150,
        kcal=350,
        emoji="🥪",
        advice="Длинный совет не должен попадать в список.",
    )
    line = _entry_line(1, entry, "Europe/Samara")
    assert line == "1. 11:20 🥪 бутерброд из гриля, 150г — 350 ккал"
    assert "Длинный совет" not in line


def test_today_view_shows_all_entries_grouped_by_meal() -> None:
    entries = [
        SimpleNamespace(
            id=index,
            created_at=datetime(2026, 5, 19, 6 + index, 0, tzinfo=UTC),
            food_name=f"еда {index}",
            weight_g=100,
            kcal=100,
            emoji="🍽️",
            advice=None,
        )
        for index in range(1, 8)
    ]
    summary = SimpleNamespace(
        kcal=700,
        target_kcal=2000,
        activity_kcal=0,
        protein=45,
        target_protein=120,
        fat=30,
        target_fat=70,
        carbs=110,
        target_carbs=230,
        entries=entries,
    )
    text, _ = _today_view(summary, 800, patterns=None, include_advice=False)
    assert "🍽 По приёмам" not in text
    assert "🚦 Сигналы" not in text
    assert "🕘 Последние записи" not in text
    assert "…ещё" not in text
    assert "🌅 Завтрак - 100 ккал" in text
    assert "☀️ Обед - 400 ккал" in text
    assert "🍿 Перекусы - 200 ккал" in text
    assert "7. " in text


def test_full_today_view_groups_entries_by_meal() -> None:
    entries = [
        SimpleNamespace(
            id=1,
            created_at=datetime(2026, 5, 19, 4, 30, tzinfo=UTC),
            food_name="завтрак",
            weight_g=None,
            kcal=300,
            emoji="🥣",
            advice=None,
        ),
        SimpleNamespace(
            id=2,
            created_at=datetime(2026, 5, 19, 9, 30, tzinfo=UTC),
            food_name="обед",
            weight_g=None,
            kcal=500,
            emoji="🍲",
            advice=None,
        ),
        SimpleNamespace(
            id=3,
            created_at=datetime(2026, 5, 19, 15, 30, tzinfo=UTC),
            food_name="ужин",
            weight_g=None,
            kcal=600,
            emoji="🍗",
            advice=None,
        ),
    ]
    labels = [label for label, _ in _entries_by_meal(entries, "Europe/Samara")]
    assert labels == ["🌅 Завтрак", "☀️ Обед", "🌙 Ужин", "🍿 Перекусы"]
    meal_lines = _meal_summary_lines(entries, "Europe/Samara")
    assert any("🌅 Завтрак: 300 ккал" in line for line in meal_lines)
    assert any("☀️ Обед: 500 ккал" in line for line in meal_lines)
    assert any("🌙 Ужин: 600 ккал" in line for line in meal_lines)


def test_smart_problem_signals_prioritize_key_issues() -> None:
    summary = SimpleNamespace(
        kcal=2300,
        target_kcal=2000,
        protein=60,
        target_protein=120,
        fat=95,
        target_fat=70,
        entries=[SimpleNamespace()],
    )
    signals = smart_problem_signals(summary, water_ml=700)
    assert len(signals) == 2
    assert "Калории выше цели" in signals[0]


def test_food_entries_keyboard_starts_compact() -> None:
    keyboard = food_entries_keyboard([10, 11, 12])
    rows = keyboard.inline_keyboard
    assert len(rows) == 1
    assert rows[0][0].callback_data == "entry:manage"
    assert rows[0][1].callback_data == "coach:meal"


def test_food_entries_keyboard_expands_entry_actions() -> None:
    keyboard = food_entries_keyboard([10, 11], expanded=True)
    rows = keyboard.inline_keyboard
    assert rows[0][0].callback_data == "entry:edit:10"
    assert rows[0][1].callback_data == "entry:delete:10"
    assert rows[0][2].callback_data == "entry:fav:10"
    assert rows[0][3].callback_data == "entry:refine:10"
    assert rows[-1][0].callback_data == "nav:today"
    assert rows[-1][1].callback_data == "coach:meal"


def test_weight_chart_returns_sparkline_for_recent_logs() -> None:
    logs = [
        SimpleNamespace(weight_kg=80.0),
        SimpleNamespace(weight_kg=79.5),
        SimpleNamespace(weight_kg=79.0),
    ]
    text = _weight_chart(logs)
    assert "График" in text
    assert "79.0-80.0 кг" in text


def test_week_highlights_name_best_day_and_average_protein() -> None:
    analytics = SimpleNamespace(
        average_kcal=2050,
        target_kcal=2000,
        days=[
            SimpleNamespace(date_label="18.05", kcal=2600, protein=70, entries_count=2),
            SimpleNamespace(date_label="19.05", kcal=1980, protein=110, entries_count=3),
        ],
    )
    lines = _week_highlight_lines(analytics)
    assert any("19.05" in line for line in lines)
    assert any("90 г/день" in line for line in lines)


def test_habit_lines_show_streaks_and_coverage() -> None:
    habits = SimpleNamespace(
        food_streak_days=4,
        water_streak_days=2,
        weight_streak_days=1,
        tracked_food_days_30=20,
        tracked_water_days_30=12,
        tracked_weight_days_30=5,
        best_habit="еда",
    )
    text = "\n".join(_habit_lines(habits))
    assert "Еда: 4 дн. подряд, 20/30 дней." in text
    assert "Сильная привычка сейчас: еда." in text


def test_month_summary_helpers_choose_focus() -> None:
    assert "перебор" in _month_delta_line(260)
    assert "недобор" in _month_delta_line(-420)
    assert _month_focus(50, 70) == "поднять белок в обычных приёмах пищи"
    assert _month_focus(260, 95) == "найти 1-2 частых источника лишних калорий"


def test_photo_recognition_user_text_includes_caption_hint() -> None:
    text = photo_recognition_user_text("это половина порции, плюс 30 г соуса")
    assert "Уточнение пользователя" in text
    assert "половина порции" in text
    assert "30 г соуса" in text


def test_photo_confirmation_can_show_portion_hint() -> None:
    text = _format_estimate_confirmation(
        FoodEstimate(name="паста", weight_g=300, kcal=600),
        show_portion_hint=True,
    )
    assert "соус" in text
    assert "напиток" in text


def test_photo_confirmation_keyboard_includes_question_buttons() -> None:
    keyboard = food_confirmation_keyboard(
        "food",
        allow_refine=True,
        allow_portions=True,
        allow_photo_questions=True,
    )
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert "food:ask:sauce" in callbacks
    assert "food:ask:drink" in callbacks
    assert "food:portion:0.5" in callbacks


def test_scale_estimate_uses_original_portion_ratio() -> None:
    estimate = FoodEstimate(name="паста", weight_g=300, kcal=600, protein=20, fat=18, carbs=90)
    scaled = _scale_estimate(estimate, 0.5)
    assert scaled.weight_g == 150
    assert scaled.kcal == 300
    assert scaled.carbs == 45


def test_food_refinement_user_text_includes_current_estimate_and_hint() -> None:
    estimate = FoodEstimate(name="сырники", weight_g=160, kcal=330, protein=18)
    text = food_refinement_user_text(estimate, "ещё полито джемом")
    assert "Текущая оценка еды" in text
    assert "сырники" in text
    assert "ещё полито джемом" in text


def test_estimate_from_entry_keeps_saved_entry_macros() -> None:
    entry = SimpleNamespace(
        food_name="паста",
        kcal=600,
        protein=20,
        fat=18,
        carbs=90,
        weight_g=300,
        emoji="🍝",
        advice="Проверь соус.",
        confidence=0.72,
    )
    estimate = estimate_from_entry(entry)
    assert estimate.name == "паста"
    assert estimate.weight_g == 300
    assert estimate.confidence == 0.72


def test_entry_time_label_uses_user_timezone_for_utc_timestamp() -> None:
    assert (
        _entry_time_label(datetime(2026, 5, 19, 7, 48, tzinfo=UTC), "Europe/Samara")
        == "11:48"
    )


def test_entry_time_label_treats_naive_timestamp_as_utc() -> None:
    assert _entry_time_label(datetime(2026, 5, 19, 7, 48), "Europe/Samara") == "11:48"


def test_reminder_meal_detection_uses_user_timezone() -> None:
    entries = [SimpleNamespace(created_at=datetime(2026, 5, 19, 8, 30, tzinfo=UTC))]
    assert _has_meal_entry(entries, "Europe/Samara", "lunch")
    assert not _has_meal_entry(entries, "Europe/Samara", "breakfast")


def test_inactivity_reminder_waits_for_three_silent_days() -> None:
    now = datetime(2026, 5, 20, 12, 5, tzinfo=UTC)
    assert _inactivity_reminder_due(
        now,
        latest_entry_at=now - timedelta(days=3, minutes=1),
        user_created_at=now - timedelta(days=20),
        last_sent_date=None,
    )
    assert not _inactivity_reminder_due(
        now,
        latest_entry_at=now - timedelta(days=2),
        user_created_at=now - timedelta(days=20),
        last_sent_date=None,
    )


def test_inactivity_reminder_repeats_at_most_weekly() -> None:
    now = datetime(2026, 5, 20, 12, 5, tzinfo=UTC)
    assert not _inactivity_reminder_due(
        now,
        latest_entry_at=now - timedelta(days=10),
        user_created_at=now - timedelta(days=20),
        last_sent_date=date(2026, 5, 16),
    )


def test_inactivity_reminder_text_is_soft_return() -> None:
    text = _inactivity_reminder_text(
        latest_entry_at=datetime(2026, 5, 17, 8, 0, tzinfo=UTC),
        user_created_at=datetime(2026, 5, 1, 8, 0, tzinfo=UTC),
        timezone_name="Europe/Samara",
    )
    assert "Вернёмся мягко" in text
    assert "один приём пищи" in text


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


def test_apple_health_shortcut_text_contains_endpoint_and_payload() -> None:
    text = _apple_health_shortcut_text("https://example.com/integrations/apple-health/token")
    assert "Получить содержимое URL" in text
    assert "https://example.com/integrations/apple-health/token" in text
    assert '"steps": 8200' in text
    assert "разницу с прошлой" in text


def test_settings_keyboard_has_apple_health_button() -> None:
    callbacks = [
        button.callback_data
        for row in settings_keyboard().inline_keyboard
        for button in row
    ]
    assert "settings:apple-health" in callbacks


def test_steps_to_kcal_estimate_is_conservative() -> None:
    assert _steps_to_kcal(10000) == 400


def test_apple_health_extracts_shortcuts_numeric_shapes() -> None:
    assert _extract_numeric_value(8200) == 8200
    assert _extract_numeric_value("8200") == 8200
    assert _extract_numeric_value({"value": 8200}) == 8200
    assert _extract_numeric_value({"quantity": {"doubleValue": 8200}}) == 8200
    assert _extract_numeric_value({"sample": {"quantity": {"doubleValue": "8200"}}}) == 8200
    assert _extract_numeric_value({"value": 4, "quantity": {"doubleValue": 70}}) == 70
    assert _extract_numeric_value({"healthKit": {"energy": {"doubleValue": 70}}}) == 70


def test_apple_health_sums_shortcuts_sample_lists_for_activity() -> None:
    assert _extract_numeric_total(
        [
            {"quantity": {"doubleValue": 4.455}},
            {"quantity": {"doubleValue": "12.5"}},
            {"value": 1.0},
        ]
    ) == 17.955
    payload, errors = _normalize_apple_health_payload(
        {
            "active_kcal": {
                "samples": [
                    {"quantity": {"doubleValue": 4.455}},
                    {"quantity": {"doubleValue": 133.545}},
                ]
            }
        }
    )
    assert errors == {}
    assert payload.active_kcal == 138


def test_apple_health_normalizes_payload_and_ignores_unknown_fields() -> None:
    payload, errors = _normalize_apple_health_payload(
        {
            "weight_kg": {"value": "74.5", "unit": "kg"},
            "steps": {"quantity": {"doubleValue": 8200}},
            "active_kcal": "340",
            "unknown": {"not": "used"},
        }
    )
    assert errors == {}
    assert payload.weight_kg == 74.5
    assert payload.steps == 8200
    assert payload.active_kcal == 340
    assert payload.has_values


def test_apple_health_normalization_keeps_valid_fields_when_one_is_invalid() -> None:
    payload, errors = _normalize_apple_health_payload(
        {
            "weight_kg": {"value": 74.5},
            "steps": {"value": "not a number"},
        }
    )
    assert payload.weight_kg == 74.5
    assert payload.steps is None
    assert errors == {"steps": "Could not extract numeric value"}
