from __future__ import annotations

import pytest

from kcal_tracker.config import Settings, validate_production_settings


def test_validate_production_settings_ignores_local_environment() -> None:
    settings = Settings(app_env="local", telegram_bot_token="", openai_api_key="")

    validate_production_settings(settings)


def test_validate_production_settings_reports_missing_required_values() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="",
        openai_api_key="",
        database_url="",
        redis_url="",
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_settings(settings)

    message = str(exc_info.value)
    assert "TELEGRAM_BOT_TOKEN" in message
    assert "OPENAI_API_KEY" in message
    assert "DATABASE_URL" in message
    assert "REDIS_URL" in message


def test_validate_production_settings_accepts_required_values() -> None:
    settings = Settings(
        app_env="production",
        telegram_bot_token="telegram-token",
        openai_api_key="openai-key",
        database_url="postgresql+asyncpg://user:pass@postgres:5432/kcal",
        redis_url="redis://redis:6379/0",
    )

    validate_production_settings(settings)
