import asyncio
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from starlette.requests import Request

from kcal_tracker.admin_bot.main import (
    _broadcast_segment_allowed,
    _broadcast_segment_keyboard,
    _compact_event_details,
    _funnel_period_text,
    _landing_period_text,
    _payment_line,
    _paywall_variant_lines,
    _paywall_variant_metrics,
    _percent,
    _quality_event_line,
    _user_quality_line,
)
from kcal_tracker.api import apple_health, routes
from kcal_tracker.api.apple_health import (
    apple_health_payload_summary,
    ensure_apple_health_import_allowed,
    extract_numeric_total,
    extract_numeric_value,
    normalize_apple_health_payload,
    read_apple_health_payload,
    steps_to_kcal,
)
from kcal_tracker.bot.handlers.diary import (
    ADVANCED_PATTERNS_UPSELL,
    _day_offset_title,
    _entries_by_meal,
    _entry_line,
    _entry_time_label,
    _habit_lines,
    _meal_summary_lines,
    _month_delta_line,
    _month_focus,
    _next_step_line,
    _today_view,
    _week_highlight_lines,
    _weight_chart,
)
from kcal_tracker.bot.handlers.food import (
    _format_estimate_confirmation,
    _format_saved_food,
    _looks_like_complex_food,
    _scale_estimate,
    _should_use_ai_first,
)
from kcal_tracker.bot.handlers.payments import (
    _payment_choice_from_callback,
    _payment_error_message,
    _payment_next_step_lines,
)
from kcal_tracker.bot.handlers.profile import _apple_health_shortcut_text, _parse_birth_date
from kcal_tracker.bot.keyboards import (
    activity_menu_keyboard,
    entry_edit_keyboard,
    food_confirmation_keyboard,
    food_entries_keyboard,
    food_recovery_keyboard,
    food_tools_keyboard,
    settings_keyboard,
    smart_after_food_save_keyboard,
    subscription_bonuses_keyboard,
    subscription_payment_method_keyboard,
    subscription_plan_keyboard,
)
from kcal_tracker.bot.text_parsing import (
    looks_like_activity,
    parse_activity_kcal,
    parse_int_from_text,
)
from kcal_tracker.models import Payment, PromoCode, QualityEvent, User
from kcal_tracker.schemas import (
    FoodEntryCreate,
    FoodEstimate,
    WebAppQualityEventCreate,
    WebAppToday,
    WebAppWeeklyMission,
    WebAppWeeklyMissions,
)
from kcal_tracker.services.ai_food import food_refinement_user_text, photo_recognition_user_text
from kcal_tracker.services.diary import (
    NutritionPatterns,
    _matches_food_history_query,
    estimate_from_entry,
)
from kcal_tracker.services.food_insights import enrich_food_payload, food_advice, food_emoji
from kcal_tracker.services.growth import _referral_code_from_payload, progress_share_url
from kcal_tracker.services.media import _sample_timestamps
from kcal_tracker.services.nutrition import (
    automatic_pattern_notes,
    daily_focus,
    end_of_day_forecast,
    high_calorie_add_warning,
    is_high_calorie_food,
    meal_suggestion_text,
    personal_style_insight,
    remaining_advice,
    smart_day_coach,
    smart_problem_signals,
    suspicious_food_warning,
    tomorrow_micro_plan,
    weekly_coach_note,
    weekly_score,
)
from kcal_tracker.services.profile import age_from_birth_date, weight_goal_summary
from kcal_tracker.services.reminders import (
    _has_meal_entry,
    _inactivity_reminder_due,
    _inactivity_reminder_text,
    evening_close_keyboard,
    return_to_diary_keyboard,
)
from kcal_tracker.services.share_cards import _wrap_card_lines
from kcal_tracker.services.subscriptions import (
    SUBSCRIPTION_PAYLOAD,
    YOOKASSA_PAYLOAD,
    SubscriptionService,
    _discounted_amount,
    normalize_promo_code,
    payload_with_promo,
    promo_is_available,
)
from kcal_tracker.services.throttle import ThrottleLimitReached


def _request_with_body(body: bytes, headers: dict[str, str] | None = None) -> Request:
    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope, receive)


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one(self) -> object:
        if self.value is None:
            raise AssertionError("Expected a scalar value")
        return self.value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class _PaymentSessionStub:
    def __init__(
        self,
        *,
        user: User,
        payment: Payment | None = None,
        execute_values: list[object] | None = None,
    ) -> None:
        self.user = user
        self.execute_values = execute_values if execute_values is not None else []
        if payment is not None:
            self.execute_values.append(payment)
        self.commits = 0
        self.refreshes = 0

    async def execute(self, _statement: object) -> _ScalarResult:
        if self.execute_values:
            return _ScalarResult(self.execute_values.pop(0))
        return _ScalarResult(self.user)

    async def get(self, model: type[object], _id: int) -> object | None:
        if model is User:
            return self.user
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _instance: object) -> None:
        self.refreshes += 1

    async def rollback(self) -> None:
        pass


def test_confidence_must_be_less_than_one() -> None:
    estimate = FoodEstimate(name="Латте", kcal=120, confidence=0.99)
    assert estimate.confidence == 0.99


def test_webapp_today_accepts_yesterday_diary() -> None:
    diary = {
        "kcal": 500,
        "protein": 20,
        "fat": 18,
        "carbs": 55,
        "activity_kcal": 0,
        "base_target_kcal": 2200,
        "target_kcal": 2200,
        "target_protein": 110,
        "target_fat": 73,
        "target_carbs": 276,
        "entries": [],
    }
    payload = WebAppToday.model_validate(
        {
            "user": {
                "id": 1,
                "telegram_id": 1,
                "username": None,
                "timezone": "Europe/Samara",
                "daily_kcal_target": 2200,
                "created_at": datetime(2026, 6, 17, tzinfo=UTC),
            },
            "diary": diary,
            "yesterday_diary": {**diary, "kcal": 900},
            "water_ml": 0,
            "latest_weight_kg": None,
            "ai_usage": {"used_today": 0, "remaining_today": 3, "daily_limit": 3},
            "weight_goal": {
                "goal": None,
                "current_weight_kg": None,
                "target_weight_kg": None,
                "weekly_weight_change_kg": None,
                "daily_kcal_target": 2200,
                "forecast_weeks": None,
                "forecast_text": "Цель не настроена",
            },
        }
    )

    assert payload.yesterday_diary is not None
    assert payload.yesterday_diary.kcal == 900


def test_apple_health_log_summary_does_not_include_raw_values() -> None:
    summary = apple_health_payload_summary(
        {
            "weight_kg": 82.4,
            "steps": [{"value": 1200}, {"value": 800}],
            "active_kcal": "345 kcal",
            "note": "Morning sync",
            "device": "iPhone",
        }
    )

    assert summary == {
        "fields": ["weight_kg", "steps", "active_kcal", "note"],
        "extra_field_count": 1,
    }
    assert "82.4" not in str(summary)
    assert "Morning sync" not in str(summary)


def test_apple_health_payload_rejects_oversized_body(monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "apple_health_payload_max_bytes", 12)
    request = _request_with_body(b'{"steps": 1000}', headers={"content-length": "15"})

    try:
        asyncio.run(read_apple_health_payload(request))
    except HTTPException as exc:
        assert exc.status_code == 413
    else:
        raise AssertionError("Oversized Apple Health payload was accepted")


def test_apple_health_import_throttle_maps_to_429(monkeypatch) -> None:
    async def blocked_rate_limit(key: str, *, limit: int, window_seconds: int) -> None:
        raise ThrottleLimitReached(23)

    monkeypatch.setattr(apple_health, "ensure_rate_limit", blocked_rate_limit)
    request = _request_with_body(b"{}")

    try:
        asyncio.run(ensure_apple_health_import_allowed("token", request))
    except HTTPException as exc:
        assert exc.status_code == 429
        assert exc.headers == {"Retry-After": "23"}
    else:
        raise AssertionError("Apple Health throttle did not raise HTTPException")


def test_weight_goal_forecast_for_loss() -> None:
    user = SimpleNamespace(
        goal="loss",
        weight=82.0,
        target_weight_kg=76.0,
        weekly_weight_change_kg=0.5,
        daily_kcal_target=1900,
    )

    summary = weight_goal_summary(user)

    assert summary.forecast_weeks == 12
    assert "дефиците" in summary.forecast_text


def test_weight_goal_forecast_rejects_wrong_direction() -> None:
    user = SimpleNamespace(
        goal="loss",
        weight=82.0,
        target_weight_kg=85.0,
        weekly_weight_change_kg=0.5,
        daily_kcal_target=1900,
    )

    summary = weight_goal_summary(user)

    assert summary.forecast_weeks is None
    assert "Проверь цель" in summary.forecast_text


def test_admin_funnel_formats_conversion_rates() -> None:
    text = _funnel_period_text(
        "7 дней",
        {
            "started": 10,
            "onboarded": 7,
            "first_food": 6,
            "active_3_days": 3,
            "ai_users": 4,
            "payers": 1,
            "webapp_first_food": 2,
            "webapp_food_saved": 5,
            "webapp_paywall": 4,
            "webapp_subscription_view": 3,
            "webapp_payment_start": 2,
            "webapp_ai_review": 3,
            "webapp_ai_reject": 1,
            "paywall_variants": {"speed": {"open": 10, "subscribe": 3, "manual": 2}},
        },
    )

    assert _percent(3, 10) == "30%"
    assert "3 активных дня: 3 (30%)" in text
    assert "Mini App оплата: paywall 4 -> подписка 3 -> старт 2" in text
    assert "speed: open 10, купить 3 (30%), вручную 2" in text


def test_paywall_variant_metrics_group_events() -> None:
    metrics = _paywall_variant_metrics(
        [
            ("webapp_paywall_open", {"paywall_variant": "speed"}),
            ("webapp_paywall_subscribe", {"paywall_variant": "speed"}),
            ("webapp_paywall_manual", {"paywall_variant": "features"}),
        ]
    )

    assert metrics == {
        "features": {"open": 0, "subscribe": 0, "manual": 1},
        "speed": {"open": 1, "subscribe": 1, "manual": 0},
    }
    assert _paywall_variant_lines(metrics)[1] == "· speed: open 1, купить 1 (100%), вручную 0"


def test_admin_user_quality_line_summarizes_problem_signals() -> None:
    text = _user_quality_line(
        {
            "webapp_ai_failed": 2,
            "food_ai_failed": 1,
            "webapp_ai_reject": 3,
            "webapp_packaged_unverified": 4,
            "webapp_paywall_open": 5,
            "webapp_payment_start": 1,
        }
    )

    assert text == "Качество 7д: AI fail 3, не то 3, упаковки 4, paywall 5 -> start 1"


def test_admin_user_payment_and_event_lines_are_compact() -> None:
    payment = Payment(
        status="pending",
        method="sbp",
        amount_kopecks=29900,
        payload="payload",
        promo_code="START20",
        created_at=datetime(2026, 6, 17, 8, 30, tzinfo=UTC),
    )
    event = QualityEvent(
        event_type="webapp_packaged_unverified",
        source="photo",
        query="Bombbar фисташковая меренга",
        details={"photos": 2, "count": 1, "paywall_variant": "speed"},
        created_at=datetime(2026, 6, 17, 8, 31, tzinfo=UTC),
    )

    assert "pending sbp 299 ₽, promo START20" in _payment_line(payment)
    assert _compact_event_details(event.details) == " (photos=2, count=1, paywall_variant=speed)"
    assert "webapp_packaged_unverified/photo" in _quality_event_line(event)


def test_webapp_quality_event_accepts_product_analytics_events() -> None:
    payload = WebAppQualityEventCreate(
        event_type="webapp_payment_start",
        source="subscription",
        details={"plan": "basic", "renewal": False},
    )

    assert payload.event_type == "webapp_payment_start"


def test_webapp_quality_event_accepts_launch_funnel_events() -> None:
    for event_type in (
        "webapp_packaged_unverified",
        "webapp_paywall_subscribe",
        "webapp_paywall_manual",
        "webapp_promo_apply",
    ):
        payload = WebAppQualityEventCreate(event_type=event_type, source="webapp")

        assert payload.event_type == event_type


def test_admin_landing_formats_click_rate() -> None:
    text = _landing_period_text(
        "7 дней",
        {"views": 100, "visitors": 72, "sessions": 81, "clicks": 12},
    )

    assert "Визиты: 100" in text
    assert "Уникальные: 72" in text
    assert "Клики в Telegram: 12 (12%)" in text


def test_admin_broadcast_all_segment_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "admin_broadcast_all_enabled", False)

    assert _broadcast_segment_allowed("active_7") is True
    assert _broadcast_segment_allowed("all") is False

    labels = [
        button.text
        for row in _broadcast_segment_keyboard("active_7").inline_keyboard
        for button in row
    ]
    assert "Все (выкл)" in labels


def test_admin_broadcast_all_segment_can_be_enabled(monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "admin_broadcast_all_enabled", True)

    assert _broadcast_segment_allowed("all") is True


def test_food_insights_add_emoji_and_advice() -> None:
    estimate = enrich_food_payload(FoodEstimate(name="шоколадный торт", kcal=420, carbs=55))
    assert estimate.emoji == "🍫"
    assert estimate.advice is not None
    assert "сахара" in estimate.advice


def test_food_insights_detect_common_foods() -> None:
    assert food_emoji("гречка с курицей") == "🥣"
    assert "Белка" in food_advice("курица", kcal=220, protein=35, fat=6, carbs=0)


def test_referral_payload_parsing() -> None:
    assert _referral_code_from_payload("ref_abc123") == "abc123"
    assert _referral_code_from_payload("start") is None


def test_progress_share_url_encodes_text() -> None:
    url = progress_share_url("Мой прогресс: 8/10")
    assert url.startswith("https://t.me/share/url?text=")
    assert "%D0%9C%D0%BE%D0%B9" in url


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


def test_remaining_advice_is_soft_when_over_target() -> None:
    summary = SimpleNamespace(
        kcal=2350,
        target_kcal=2100,
        protein=100,
        target_protein=110,
    )
    text = remaining_advice(summary)
    assert "выше цели" in text
    assert "Без наказаний" in text


def test_history_source_is_valid_for_saved_food() -> None:
    payload = FoodEntryCreate(name="Барни", kcal=120, weight_g=30, source="history")
    assert payload.source == "history"


def test_saved_food_text_adds_mini_goal() -> None:
    estimate = FoodEstimate(name="Творог", kcal=180, protein=25, fat=5, carbs=8, weight_g=150)
    summary = SimpleNamespace(
        kcal=1350,
        target_kcal=2100,
        protein=70,
        target_protein=120,
    )
    text = _format_saved_food(estimate, summary=summary, water_ml=800)
    assert "Мини-цель" in text
    assert "белка" in text


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


def test_personal_style_and_tomorrow_plan_use_patterns() -> None:
    analytics = SimpleNamespace(
        average_kcal=2050,
        target_kcal=2000,
        days_in_target=3,
        days=[
            SimpleNamespace(entries_count=2, kcal=1900, protein=65, fat=70, carbs=240),
            SimpleNamespace(entries_count=3, kcal=2100, protein=72, fat=80, carbs=260),
            SimpleNamespace(entries_count=2, kcal=2050, protein=78, fat=70, carbs=250),
        ],
    )
    patterns = NutritionPatterns(
        tracked_days=5,
        average_evening_kcal=520,
        no_breakfast_days=3,
        no_breakfast_over_target_days=2,
        sweet_drink_days=0,
        sweet_drink_average_delta=0,
    )

    assert "без завтрака" in personal_style_insight(analytics, patterns)
    assert "белок" in tomorrow_micro_plan(analytics, patterns)


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


def test_today_view_shows_activity_and_manage_button() -> None:
    summary = SimpleNamespace(
        kcal=700,
        target_kcal=2200,
        base_target_kcal=2150,
        activity_kcal=50,
        protein=45,
        target_protein=120,
        fat=30,
        target_fat=70,
        carbs=110,
        target_carbs=230,
        entries=[],
    )
    activities = [
        SimpleNamespace(
            id=1,
            created_at=datetime(2026, 5, 19, 8, 0, tzinfo=UTC),
            activity_name="Apple Health active energy",
            kcal=50,
        )
    ]
    text, keyboard = _today_view(
        summary,
        800,
        activities=activities,
        patterns=None,
        include_advice=False,
    )
    assert "🏃 Активность" in text
    assert "Apple Health active energy — 50 ккал" in text
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert "activity:manage" not in callbacks
    activity_callbacks = [
        button.callback_data
        for row in activity_menu_keyboard([1]).inline_keyboard
        for button in row
    ]
    assert "activity:custom" in activity_callbacks
    assert "activity:manage" in activity_callbacks


def test_today_view_links_to_yesterday() -> None:
    summary = SimpleNamespace(
        kcal=0,
        target_kcal=2200,
        activity_kcal=0,
        protein=0,
        target_protein=120,
        fat=0,
        target_fat=70,
        carbs=0,
        target_carbs=230,
        entries=[],
    )

    _, keyboard = _today_view(summary, 0, include_advice=False)

    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert "diary:yesterday" in callbacks


def test_yesterday_view_links_to_today_and_card() -> None:
    summary = SimpleNamespace(
        kcal=700,
        target_kcal=2200,
        activity_kcal=0,
        protein=45,
        target_protein=120,
        fat=30,
        target_fat=70,
        carbs=110,
        target_carbs=230,
        entries=[],
    )

    text, keyboard = _today_view(
        summary,
        800,
        title="📊 Вчера, 21.05",
        mode="yesterday",
        include_advice=False,
    )

    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert "📊 Вчера, 21.05" in text
    assert "nav:today" in callbacks
    assert "day:yesterday-card" in callbacks
    assert "diary:yesterday" not in callbacks


def test_day_offset_title_formats_yesterday(monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 22, 12, 0, tzinfo=tz)

    monkeypatch.setattr("kcal_tracker.bot.handlers.diary_formatting.datetime", FixedDateTime)

    assert _day_offset_title("Europe/Samara", days_ago=1) == "📊 Вчера, 21.05"


def test_wrap_card_lines_keeps_food_lines_readable() -> None:
    lines = _wrap_card_lines(
        [
            "бутерброд из гриля — 700 ккал",
            "жареная картошка с мясом — 350 ккал",
            "круассан с сыром и колбаской — 350 ккал",
        ],
        max_chars=48,
    )

    assert len(lines) == 3
    assert all(len(line) <= 48 for line in lines)
    assert "бутерброд из гриля" in lines[0]


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
    assert rows[0][2].callback_data == "diary:yesterday"


def test_food_entries_keyboard_expands_entry_actions() -> None:
    keyboard = food_entries_keyboard([10, 11], expanded=True)
    rows = keyboard.inline_keyboard
    assert rows[0][0].callback_data == "entry:edit:10"
    assert rows[0][1].callback_data == "entry:delete:10"
    assert rows[0][2].callback_data == "entry:fav:10"
    assert rows[0][3].callback_data == "entry:refine:10"
    assert rows[-1][0].callback_data == "nav:today"
    assert rows[-1][1].callback_data == "coach:meal"


def test_after_food_save_keyboard_has_fast_correction_actions() -> None:
    keyboard = smart_after_food_save_keyboard(entry_id=42, kcal_left=300, protein_left=35)
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert callbacks[:4] == ["nav:today", "nav:add-food", "entry:edit-menu:42", "entry:fav:42"]
    assert "coach:meal" in callbacks
    assert callbacks[-1] == "entry:delete:42"


def test_entry_edit_keyboard_has_manual_correction_fields() -> None:
    keyboard = entry_edit_keyboard(42)
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert "entry:edit:42" in callbacks
    assert "entry:edit-name:42" in callbacks
    assert "entry:edit-kcal:42" in callbacks
    assert "entry:edit-macros:42" in callbacks


def test_today_next_step_prioritizes_protein() -> None:
    summary = SimpleNamespace(
        kcal=1300,
        target_kcal=2100,
        protein=60,
        target_protein=120,
        entries=[SimpleNamespace()],
    )
    assert _next_step_line(summary, water_ml=1500) == "Следующий шаг: добрать белок."


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


def test_history_confirmation_keyboard_can_recover_wrong_match() -> None:
    keyboard = food_confirmation_keyboard(
        "food",
        allow_ai_retry=True,
        allow_database_retry=True,
        allow_split=True,
    )
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert "food:ai" in callbacks
    assert "food:search" in callbacks
    assert "food:split" in callbacks
    assert "food:wrong" in callbacks


def test_food_recovery_keyboard_has_safe_next_steps() -> None:
    keyboard = food_recovery_keyboard()
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]

    assert callbacks == ["food:ai", "food:search", "nav:add-food", "support:open"]


def test_food_tools_keyboard_can_delete_last_entry() -> None:
    keyboard = food_tools_keyboard(has_frequent_foods=False, has_yesterday_entries=False)
    callbacks = [
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
    ]
    assert "entry:delete-last" in callbacks


def test_compound_text_prefers_ai_first() -> None:
    assert _should_use_ai_first("латте и два банана") is True
    assert _should_use_ai_first("курица рис салат") is True
    assert _should_use_ai_first("латте") is False


def test_history_match_does_not_match_short_entry_inside_long_query() -> None:
    assert _matches_food_history_query("барни", "барни") is True
    assert _matches_food_history_query("барни", "барни банановый") is True
    assert _matches_food_history_query("мой барни", "барни банановый") is True
    assert _matches_food_history_query("барни пироженное", "барни") is False


def test_complex_food_detection_is_selective() -> None:
    assert _looks_like_complex_food("паста с курицей") is True
    assert _looks_like_complex_food("салат цезарь") is True
    assert _looks_like_complex_food("барни") is False


def test_suspicious_food_warning_flags_unrealistic_values() -> None:
    warning = suspicious_food_warning(FoodEstimate(name="батончик", weight_g=30, kcal=900))
    assert warning is not None
    assert "странно" in warning
    assert suspicious_food_warning(FoodEstimate(name="салат", weight_g=250, kcal=180)) is None


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


def test_evening_close_keyboard_has_fast_day_actions() -> None:
    callbacks = [
        button.callback_data
        for row in evening_close_keyboard().inline_keyboard
        for button in row
    ]

    assert callbacks == ["nav:add-food", "water:add:250", "nav:today"]


def test_return_to_diary_keyboard_has_retention_actions() -> None:
    callbacks = [
        button.callback_data
        for row in return_to_diary_keyboard().inline_keyboard
        for button in row
    ]

    assert callbacks == ["nav:add-food", "nav:today", "nav:reminders"]


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
    assert "settings:birth-date" in callbacks
    assert "settings:age" not in callbacks


def test_birth_date_parser_accepts_common_formats() -> None:
    assert _parse_birth_date("14.08.1998") == date(1998, 8, 14)
    assert _parse_birth_date("1998-08-14") == date(1998, 8, 14)
    assert _parse_birth_date("14/08/1998") == date(1998, 8, 14)


def test_birth_date_parser_rejects_implausible_age() -> None:
    assert _parse_birth_date("14.08.2024") is None
    assert _parse_birth_date("14.08.1910") is None


def test_age_from_birth_date_accounts_for_birthday() -> None:
    assert age_from_birth_date(date(1998, 8, 14), today=date(2026, 8, 13)) == 27
    assert age_from_birth_date(date(1998, 8, 14), today=date(2026, 8, 14)) == 28


def test_subscription_plan_keyboard_keeps_payment_choices_separate() -> None:
    callbacks = [
        button.callback_data
        for row in subscription_plan_keyboard().inline_keyboard
        for button in row
    ]
    assert "subscription:plan:basic" in callbacks
    assert "subscription:plan:unlimited" in callbacks
    assert not any(callback.startswith("subscription:yookassa:") for callback in callbacks)


def test_subscription_payment_keyboard_shows_only_selected_plan() -> None:
    callbacks = [
        button.callback_data
        for row in subscription_payment_method_keyboard("basic").inline_keyboard
        for button in row
    ]
    assert "subscription:promo:ask:basic" in callbacks
    assert "subscription:yookassa:basic:sbp" in callbacks
    assert "subscription:yookassa:basic:auto" in callbacks
    assert "subscription:stars:basic" in callbacks
    assert "subscription:yookassa:unlimited:sbp" not in callbacks
    assert "subscription:yookassa:unlimited:auto" not in callbacks
    assert "subscription:yookassa:basic:bank_card" not in callbacks


def test_yookassa_payment_callback_defaults_to_auto_method() -> None:
    basic_plan, basic_method, basic_promo = _payment_choice_from_callback(
        "subscription:yookassa:basic:auto"
    )
    legacy_plan, legacy_method, legacy_promo = _payment_choice_from_callback(
        "subscription:yookassa:unlimited"
    )
    promo_plan, promo_method, promo = _payment_choice_from_callback(
        "subscription:yookassa:basic:sbp:START20"
    )
    assert (basic_plan.code, basic_method, basic_promo) == ("basic", "auto", None)
    assert (legacy_plan.code, legacy_method, legacy_promo) == ("unlimited", "auto", None)
    assert (promo_plan.code, promo_method, promo) == ("basic", "sbp", "START20")


def test_yookassa_invoice_activation_is_idempotent_when_payment_is_already_paid() -> None:
    until = datetime.now(UTC) + timedelta(days=12)
    user = User(id=1, telegram_id=123, subscription_expires_at=until)
    payment = Payment(
        id=10,
        user_id=user.id,
        amount_kopecks=19900,
        currency="RUB",
        method="sbp",
        status="succeeded",
        payload=f"{YOOKASSA_PAYLOAD}:basic",
        telegram_payment_charge_id="tg-charge-1",
        provider_payment_charge_id="provider-charge-1",
        paid_at=datetime.now(UTC),
    )
    session = _PaymentSessionStub(user=user, execute_values=[payment, payment])
    service = SubscriptionService(session)  # type: ignore[arg-type]

    result = asyncio.run(
        service.activate_from_yookassa_invoice_payment(
            payment=payment,
            telegram_payment_charge_id="tg-charge-1",
            provider_payment_charge_id="provider-charge-1",
        )
    )

    assert result == until
    assert user.subscription_expires_at == until
    assert session.commits == 0


def test_yookassa_poll_activation_is_idempotent_when_payment_is_already_paid() -> None:
    until = datetime.now(UTC) + timedelta(days=8)
    user = User(id=1, telegram_id=123, subscription_expires_at=until)
    payment = Payment(
        id=11,
        user_id=user.id,
        amount_kopecks=19900,
        currency="RUB",
        method="auto",
        status="succeeded",
        payload=f"{YOOKASSA_PAYLOAD}:basic",
        yookassa_payment_id="yk-payment-1",
        paid_at=datetime.now(UTC),
    )
    session = _PaymentSessionStub(user=user, payment=payment)
    service = SubscriptionService(session)  # type: ignore[arg-type]

    result = asyncio.run(service._activate_from_yookassa_payment(payment))

    assert result == until
    assert user.subscription_expires_at == until
    assert session.commits == 0


def test_promo_code_helpers_normalize_and_discount() -> None:
    assert normalize_promo_code(" start 20 ") == "START20"
    assert _discounted_amount(299, 20) == 239
    assert _discounted_amount(1, 95) == 1


def test_payload_with_promo_keeps_plan_and_normalized_code() -> None:
    assert payload_with_promo(SUBSCRIPTION_PAYLOAD, "unlimited", " start 20 ") == (
        "ai_subscription_30d:unlimited:START20"
    )
    assert payload_with_promo(SUBSCRIPTION_PAYLOAD, "unknown", None) == "ai_subscription_30d:basic"


def test_promo_availability_respects_active_expiry_and_usage_limit() -> None:
    now = datetime(2026, 6, 22, tzinfo=UTC)

    assert promo_is_available(
        PromoCode(code="LIVE", discount_percent=20, active=True, expires_at=now + timedelta(days=1)),
        now=now,
    )
    assert not promo_is_available(
        PromoCode(code="OFF", discount_percent=20, active=False, expires_at=now + timedelta(days=1)),
        now=now,
    )
    assert not promo_is_available(
        PromoCode(code="OLD", discount_percent=20, active=True, expires_at=now),
        now=now,
    )
    assert not promo_is_available(
        PromoCode(
            code="USED",
            discount_percent=20,
            active=True,
            max_uses=3,
            used_count=3,
            expires_at=now + timedelta(days=1),
        ),
        now=now,
    )


def test_subscription_bonuses_hide_refund_action() -> None:
    callbacks = [
        button.callback_data
        for row in subscription_bonuses_keyboard(
            trial_available=False,
            winback_available=False,
            refund_available=True,
        ).inline_keyboard
        for button in row
    ]
    assert "subscription:refund" in callbacks
    assert "subscription:trial" not in callbacks


def test_yookassa_credentials_error_is_user_friendly() -> None:
    message = _payment_error_message("Error in shopId or secret key. Check their validity.")
    assert "правильный ShopID" in message


def test_payment_next_steps_explain_pending_flow() -> None:
    text = "\n".join(_payment_next_step_lines())

    assert "автоматически" in text
    assert "Проверить оплату" in text
    assert "счёт истечёт" in text


def test_steps_to_kcal_estimate_is_conservative() -> None:
    assert steps_to_kcal(10000) == 400


def test_apple_health_extracts_shortcuts_numeric_shapes() -> None:
    assert extract_numeric_value(8200) == 8200
    assert extract_numeric_value("8200") == 8200
    assert extract_numeric_value({"value": 8200}) == 8200
    assert extract_numeric_value({"quantity": {"doubleValue": 8200}}) == 8200
    assert extract_numeric_value({"sample": {"quantity": {"doubleValue": "8200"}}}) == 8200
    assert extract_numeric_value({"value": 4, "quantity": {"doubleValue": 70}}) == 70
    assert extract_numeric_value({"healthKit": {"energy": {"doubleValue": 70}}}) == 70


def test_apple_health_sums_shortcuts_sample_lists_for_activity() -> None:
    assert extract_numeric_total(
        [
            {"quantity": {"doubleValue": 4.455}},
            {"quantity": {"doubleValue": "12.5"}},
            {"value": 1.0},
        ]
    ) == 17.955
    payload, errors = normalize_apple_health_payload(
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


def test_apple_health_sums_shortcuts_newline_strings_for_activity() -> None:
    payload, errors = normalize_apple_health_payload(
        {
            "steps": "72\n101\n10",
            "active_kcal": "4.455\n1.653\n131.892",
            "weight_kg": "",
        }
    )
    assert errors == {"weight_kg": "Could not extract numeric value"}
    assert payload.steps == 183
    assert payload.active_kcal == 138


def test_apple_health_normalizes_payload_and_ignores_unknown_fields() -> None:
    payload, errors = normalize_apple_health_payload(
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
    payload, errors = normalize_apple_health_payload(
        {
            "weight_kg": {"value": 74.5},
            "steps": {"value": "not a number"},
        }
    )
    assert payload.weight_kg == 74.5
    assert payload.steps is None
    assert errors == {"steps": "Could not extract numeric value"}


def test_webapp_weekly_missions_schema_exposes_bonus_state() -> None:
    missions = WebAppWeeklyMissions(
        week_start=date(2026, 6, 15),
        missions=[
            WebAppWeeklyMission(
                key="food",
                title="Еда 5 дней",
                current=5,
                target=5,
                completed=True,
            ),
            WebAppWeeklyMission(
                key="water",
                title="Вода 5 дней",
                current=3,
                target=5,
                completed=False,
            ),
        ],
        completed_count=1,
        eligible_for_bonus=False,
        bonus_claimed=False,
    )

    assert missions.week_start == date(2026, 6, 15)
    assert missions.missions[0].completed is True
    assert missions.completed_count == 1
    assert missions.eligible_for_bonus is False
