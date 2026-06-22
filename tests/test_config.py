from __future__ import annotations

import pytest

from kcal_tracker.config import Settings, parse_admin_ids, validate_production_settings
from kcal_tracker.services.webapp_auth import validate_webapp_init_data


def _signed_init_data(bot_token: str, *, auth_date: int = 1_800_000_000) -> str:
    import hashlib
    import hmac
    import json
    from urllib.parse import urlencode

    payload = {
        "auth_date": str(auth_date),
        "query_id": "test-query",
        "user": json.dumps(
            {"id": 12345, "username": "tester", "first_name": "Test"},
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


def test_validate_production_settings_ignores_local_environment() -> None:
    settings = Settings(app_env="local", telegram_bot_token="", openai_api_key="")

    validate_production_settings(settings)


def test_validate_production_settings_reports_missing_required_values() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="",
        openai_api_key="",
        public_api_url="",
        database_url="",
        redis_url="",
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_settings(settings)

    message = str(exc_info.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "OPENAI_API_KEY" in message
    assert "PUBLIC_API_URL" in message
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message


def test_validate_production_settings_rejects_local_public_api_url() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="telegram-token",
        openai_api_key="openai-key",
        public_api_url="http://127.0.0.1:3100",
        database_url="postgresql+asyncpg://user:pass@postgres:5432/kcal",
        redis_url="redis://redis:6379/0",
    )

    with pytest.raises(RuntimeError, match="PUBLIC_API_URL must not point to a local address"):
        validate_production_settings(settings)


def test_validate_production_settings_rejects_relative_public_api_url() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="telegram-token",
        openai_api_key="openai-key",
        public_api_url="/api",
        database_url="postgresql+asyncpg://user:pass@postgres:5432/kcal",
        redis_url="redis://redis:6379/0",
    )

    with pytest.raises(RuntimeError, match=r"PUBLIC_API_URL must be an absolute http\(s\) URL"):
        validate_production_settings(settings)


def test_validate_production_settings_accepts_required_values() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="telegram-token",
        openai_api_key="openai-key",
        public_api_url="https://kcal.example.com",
        database_url="postgresql+asyncpg://user:pass@postgres:5432/kcal",
        redis_url="redis://redis:6379/0",
    )

    validate_production_settings(settings)


def test_parse_admin_ids_accepts_commas_and_semicolons() -> None:
    assert parse_admin_ids("123, 456;789") == {123, 456, 789}


def test_parse_admin_ids_rejects_non_numeric_values() -> None:
    with pytest.raises(RuntimeError, match="ADMIN_TELEGRAM_IDS"):
        parse_admin_ids("123, nope")


def test_food_search_timeouts_are_configurable() -> None:
    settings = Settings(
        food_search_openfoodfacts_timeout_seconds=1.5,
        food_search_fatsecret_timeout_seconds=2.5,
    )

    assert settings.food_search_openfoodfacts_timeout_seconds == 1.5
    assert settings.food_search_fatsecret_timeout_seconds == 2.5


def test_landing_event_limits_are_configurable() -> None:
    settings = Settings(
        landing_event_rate_limit_per_minute=12,
        landing_event_dedupe_seconds=60,
    )

    assert settings.landing_event_rate_limit_per_minute == 12
    assert settings.landing_event_dedupe_seconds == 60


def test_ai_safety_limits_are_configurable() -> None:
    settings = Settings(
        ai_unlimited_safety_daily_request_limit=120,
        ai_photo_queue_concurrency=3,
        ai_photo_queue_wait_seconds=7,
        ai_photo_queue_slot_ttl_seconds=45,
        admin_ai_user_day_threshold=50,
        admin_landing_views_no_click_hour_threshold=30,
        admin_payment_starts_no_success_hour_threshold=4,
        admin_paywall_no_payment_start_hour_threshold=9,
        admin_unverified_packaged_hour_threshold=6,
    )

    assert settings.ai_unlimited_safety_daily_request_limit == 120
    assert settings.ai_photo_queue_concurrency == 3
    assert settings.ai_photo_queue_wait_seconds == 7
    assert settings.ai_photo_queue_slot_ttl_seconds == 45
    assert settings.admin_ai_user_day_threshold == 50
    assert settings.admin_landing_views_no_click_hour_threshold == 30
    assert settings.admin_payment_starts_no_success_hour_threshold == 4
    assert settings.admin_paywall_no_payment_start_hour_threshold == 9
    assert settings.admin_unverified_packaged_hour_threshold == 6


def test_log_format_is_configurable() -> None:
    settings = Settings(log_format="json")

    assert settings.log_format == "json"


def test_webapp_init_data_validation_accepts_signed_payload() -> None:
    identity = validate_webapp_init_data(
        _signed_init_data("bot-token"),
        bot_token="bot-token",
        now=1_800_000_100,
    )

    assert identity.telegram_id == 12345
    assert identity.username == "tester"


def test_webapp_init_data_validation_rejects_bad_signature() -> None:
    with pytest.raises(RuntimeError, match="Invalid init data signature"):
        validate_webapp_init_data(
            _signed_init_data("bot-token").replace("tester", "attacker"),
            bot_token="bot-token",
            now=1_800_000_100,
        )


def test_webapp_init_data_validation_rejects_expired_payload() -> None:
    with pytest.raises(RuntimeError, match="Init data is expired"):
        validate_webapp_init_data(
            _signed_init_data("bot-token", auth_date=1_800_000_000),
            bot_token="bot-token",
            now=1_800_100_000,
        )


def test_webapp_init_data_validation_rejects_missing_hash() -> None:
    payload_without_hash = "&".join(
        part for part in _signed_init_data("bot-token").split("&") if not part.startswith("hash=")
    )

    with pytest.raises(RuntimeError, match="Missing init data hash"):
        validate_webapp_init_data(
            payload_without_hash,
            bot_token="bot-token",
            now=1_800_000_100,
        )
