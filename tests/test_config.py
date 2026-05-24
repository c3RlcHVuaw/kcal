from __future__ import annotations

import pytest

from kcal_tracker.config import Settings, parse_admin_ids, validate_production_settings


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
