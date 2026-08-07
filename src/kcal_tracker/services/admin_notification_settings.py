from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kcal_tracker.models import AdminSetting

ADMIN_NOTIFICATIONS_KEY = "admin_notifications"
ADMIN_NOTIFICATION_KEYS = (
    "alerts_enabled",
    "server_alerts_enabled",
    "openai_alerts_enabled",
    "business_alerts_enabled",
    "quality_alerts_enabled",
    "recovery_enabled",
    "daily_digest_enabled",
)


@dataclass(frozen=True)
class AdminNotificationSettings:
    alerts_enabled: bool = True
    server_alerts_enabled: bool = True
    openai_alerts_enabled: bool = True
    business_alerts_enabled: bool = True
    quality_alerts_enabled: bool = True
    recovery_enabled: bool = True
    daily_digest_enabled: bool = True
    updated_at: datetime | None = None

    def as_value(self) -> dict[str, bool]:
        return {key: bool(getattr(self, key)) for key in ADMIN_NOTIFICATION_KEYS}


async def get_admin_notification_settings(
    session: AsyncSession,
) -> AdminNotificationSettings:
    setting = await session.scalar(
        select(AdminSetting).where(AdminSetting.key == ADMIN_NOTIFICATIONS_KEY)
    )
    if setting is None:
        return AdminNotificationSettings()
    return admin_notification_settings_from_value(setting.value, updated_at=setting.updated_at)


async def set_admin_notification_flag(
    session: AsyncSession,
    key: str,
    enabled: bool,
) -> AdminNotificationSettings:
    if key not in ADMIN_NOTIFICATION_KEYS:
        raise ValueError(f"Unknown admin notification flag: {key}")

    setting = await session.scalar(
        select(AdminSetting)
        .where(AdminSetting.key == ADMIN_NOTIFICATIONS_KEY)
        .with_for_update()
    )
    current = (
        admin_notification_settings_from_value(setting.value)
        if setting is not None
        else AdminNotificationSettings()
    )
    value = current.as_value()
    value[key] = enabled
    if setting is None:
        setting = AdminSetting(key=ADMIN_NOTIFICATIONS_KEY, value=value)
        session.add(setting)
    else:
        setting.value = value
    await session.commit()
    return admin_notification_settings_from_value(setting.value, updated_at=setting.updated_at)


async def toggle_admin_notification_flag(
    session: AsyncSession,
    key: str,
) -> AdminNotificationSettings:
    current = await get_admin_notification_settings(session)
    return await set_admin_notification_flag(session, key, not bool(getattr(current, key)))


def admin_notification_settings_from_value(
    value: Any,
    *,
    updated_at: datetime | None = None,
) -> AdminNotificationSettings:
    raw = value if isinstance(value, dict) else {}
    defaults = AdminNotificationSettings()
    return AdminNotificationSettings(
        alerts_enabled=_bool_value(raw.get("alerts_enabled"), defaults.alerts_enabled),
        server_alerts_enabled=_bool_value(
            raw.get("server_alerts_enabled"),
            defaults.server_alerts_enabled,
        ),
        openai_alerts_enabled=_bool_value(
            raw.get("openai_alerts_enabled"),
            defaults.openai_alerts_enabled,
        ),
        business_alerts_enabled=_bool_value(
            raw.get("business_alerts_enabled"),
            defaults.business_alerts_enabled,
        ),
        quality_alerts_enabled=_bool_value(
            raw.get("quality_alerts_enabled"),
            defaults.quality_alerts_enabled,
        ),
        recovery_enabled=_bool_value(raw.get("recovery_enabled"), defaults.recovery_enabled),
        daily_digest_enabled=_bool_value(
            raw.get("daily_digest_enabled"),
            defaults.daily_digest_enabled,
        ),
        updated_at=updated_at,
    )


def _bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled"}:
            return False
    if isinstance(value, int):
        return bool(value)
    return default
