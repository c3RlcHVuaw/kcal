from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from kcal_tracker.config import settings

WEBAPP_AUTH_MAX_AGE_SECONDS = 24 * 60 * 60


class WebAppAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class WebAppIdentity:
    telegram_id: int
    username: str | None = None
    first_name: str | None = None


def validate_webapp_init_data(
    init_data: str,
    *,
    bot_token: str = settings.telegram_bot_token,
    now: int | None = None,
) -> WebAppIdentity:
    if not bot_token:
        raise WebAppAuthError("Telegram bot token is not configured")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise WebAppAuthError("Missing init data hash")

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise WebAppAuthError("Invalid init data signature")

    auth_date = _parse_int(pairs.get("auth_date"))
    current_time = now if now is not None else int(time.time())
    if auth_date is None or current_time - auth_date > WEBAPP_AUTH_MAX_AGE_SECONDS:
        raise WebAppAuthError("Init data is expired")

    user_payload = pairs.get("user")
    if not user_payload:
        raise WebAppAuthError("Missing user payload")

    import json

    try:
        user = json.loads(user_payload)
    except json.JSONDecodeError as exc:
        raise WebAppAuthError("Invalid user payload") from exc
    telegram_id = _parse_int(user.get("id") if isinstance(user, dict) else None)
    if telegram_id is None:
        raise WebAppAuthError("Missing Telegram user id")
    return WebAppIdentity(
        telegram_id=telegram_id,
        username=user.get("username") if isinstance(user, dict) else None,
        first_name=user.get("first_name") if isinstance(user, dict) else None,
    )


def _parse_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
