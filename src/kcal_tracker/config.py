from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 3100
    public_api_url: str = "http://127.0.0.1:3100"

    database_url: str = "postgresql+asyncpg://kcal:kcal@postgres:5432/kcal"
    redis_url: str = "redis://redis:6379/0"

    telegram_bot_token: str = ""
    openai_api_key: str = ""
    openai_vision_model: str = "gpt-4o-mini"
    openai_text_model: str = "gpt-4o-mini"
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"

    default_timezone: str = "Europe/Samara"
    default_daily_kcal_target: int = 2200
    rate_limit_per_minute: int = Field(default=30, ge=1)
    ai_daily_request_limit: int = Field(default=100, ge=0)
    ai_trial_request_limit: int = Field(default=3, ge=0)
    ai_subscription_stars: int = Field(default=199, ge=1)
    ai_subscription_rub: int = Field(default=299, ge=1)
    ai_subscription_days: int = Field(default=30, ge=1)
    yookassa_provider_token: str = ""
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_return_url: str = ""
    yookassa_payment_timeout_minutes: int = Field(default=60, ge=1)
    yookassa_poll_interval_seconds: int = Field(default=30, ge=5)
    referral_reward_days: int = Field(default=7, ge=0)
    referral_active_window_days: int = Field(default=7, ge=1)
    referral_active_required_days: int = Field(default=5, ge=1)
    premium_trial_days: int = Field(default=1, ge=0)
    winback_offer_days: int = Field(default=1, ge=0)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
