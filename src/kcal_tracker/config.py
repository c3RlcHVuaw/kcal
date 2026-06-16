from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 3100
    public_api_url: str = "http://127.0.0.1:3100"
    external_api_token: str = ""

    database_url: str = "postgresql+asyncpg://kcal:kcal@postgres:5432/kcal"
    redis_url: str = "redis://redis:6379/0"

    telegram_bot_token: str = ""
    admin_bot_token: str = ""
    admin_telegram_ids: str = ""
    openai_admin_api_key: str = ""
    openai_monthly_budget_usd: float = Field(default=0.0, ge=0)
    openai_remaining_alert_usd: float = Field(default=2.0, ge=0)
    openai_api_key: str = ""
    openai_vision_model: str = "gpt-4o-mini"
    openai_text_model: str = "gpt-4o-mini"
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"
    fatsecret_client_id: str = ""
    fatsecret_client_secret: str = ""
    fatsecret_scope: str = "premier localization"
    fatsecret_region: str = "RU"
    fatsecret_language: str = "ru"
    food_search_openfoodfacts_timeout_seconds: float = Field(default=3.0, ge=0.5)
    food_search_fatsecret_timeout_seconds: float = Field(default=3.0, ge=0.5)
    landing_event_rate_limit_per_minute: int = Field(default=30, ge=1)
    landing_event_dedupe_seconds: int = Field(default=1800, ge=0)
    ai_burst_per_user_per_minute: int = Field(default=6, ge=1)
    ai_global_burst_per_minute: int = Field(default=60, ge=1)
    barcode_burst_per_user_per_minute: int = Field(default=12, ge=1)
    apple_health_import_rate_limit_per_minute: int = Field(default=12, ge=1)
    apple_health_payload_max_bytes: int = Field(default=64 * 1024, ge=1024)

    default_timezone: str = "Europe/Samara"
    default_daily_kcal_target: int = 2200
    rate_limit_per_minute: int = Field(default=30, ge=1)
    ai_daily_request_limit: int = Field(default=30, ge=0)
    ai_basic_daily_request_limit: int = Field(default=30, ge=0)
    ai_unlimited_daily_request_limit: int = Field(default=0, ge=0)
    ai_trial_request_limit: int = Field(default=3, ge=0)
    ai_subscription_stars: int = Field(default=499, ge=1)
    ai_subscription_rub: int = Field(default=299, ge=1)
    ai_unlimited_subscription_stars: int = Field(default=1199, ge=1)
    ai_unlimited_subscription_rub: int = Field(default=699, ge=1)
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
    admin_alert_interval_seconds: int = Field(default=300, ge=30)
    admin_alert_cooldown_seconds: int = Field(default=3600, ge=60)
    admin_server_load_per_cpu_threshold: float = Field(default=2.0, ge=0)
    admin_server_memory_percent_threshold: float = Field(default=90.0, ge=1, le=100)
    admin_server_disk_percent_threshold: float = Field(default=85.0, ge=1, le=100)
    admin_pending_payments_alert_threshold: int = Field(default=3, ge=1)
    admin_failed_payments_hour_threshold: int = Field(default=2, ge=1)
    admin_no_onboarding_alert_threshold: int = Field(default=5, ge=1)
    admin_quality_not_it_hour_threshold: int = Field(default=5, ge=1)
    admin_quality_ai_failed_hour_threshold: int = Field(default=3, ge=1)
    admin_quality_no_match_hour_threshold: int = Field(default=5, ge=1)
    admin_daily_digest_time: str = "09:05"
    admin_broadcast_all_enabled: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def admin_ids(self) -> set[int]:
        return parse_admin_ids(self.admin_telegram_ids)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def parse_admin_ids(value: str) -> set[int]:
    ids: set[int] = set()
    for raw_part in value.replace(";", ",").split(","):
        part = raw_part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError as exc:
            raise RuntimeError("ADMIN_TELEGRAM_IDS must contain only numeric Telegram IDs") from exc
    return ids


PRODUCTION_REQUIRED_SETTINGS = {
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "OPENAI_API_KEY": "openai_api_key",
    "PUBLIC_API_URL": "public_api_url",
    "DATABASE_URL": "database_url",
    "REDIS_URL": "redis_url",
}

LOCAL_PUBLIC_API_HOSTS = {"127.0.0.1", "0.0.0.0", "::1", "localhost"}


def validate_production_settings(settings_obj: Settings = settings) -> None:
    if not settings_obj.is_production:
        return

    missing = [
        env_name
        for env_name, field_name in PRODUCTION_REQUIRED_SETTINGS.items()
        if not str(getattr(settings_obj, field_name, "")).strip()
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing required production settings: {joined}")

    parsed_public_url = urlparse(settings_obj.public_api_url)
    if parsed_public_url.scheme not in {"http", "https"} or not parsed_public_url.netloc:
        raise RuntimeError("PUBLIC_API_URL must be an absolute http(s) URL in production")
    if parsed_public_url.hostname in LOCAL_PUBLIC_API_HOSTS:
        raise RuntimeError("PUBLIC_API_URL must not point to a local address in production")
