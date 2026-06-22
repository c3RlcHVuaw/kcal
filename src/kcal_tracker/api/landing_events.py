from __future__ import annotations

import hashlib
import logging

from redis.asyncio import Redis

from kcal_tracker.config import settings
from kcal_tracker.schemas import LandingEventCreate

logger = logging.getLogger(__name__)


def hash_landing_ip(value: str) -> str:
    salt = settings.telegram_bot_token or settings.admin_bot_token or settings.app_env
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()


async def should_record_landing_event(payload: LandingEventCreate, ip_hash: str | None) -> bool:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        visitor_key = ip_hash or payload.visitor_id or "anonymous"
        rate_key = f"landing:rate:{visitor_key}"
        request_count = await redis.incr(rate_key)
        if request_count == 1:
            await redis.expire(rate_key, 60)
        if request_count > settings.landing_event_rate_limit_per_minute:
            logger.info("Landing event rate limited key=%s type=%s", visitor_key[:12], payload.event_type)
            return False

        if payload.event_type != "view" or settings.landing_event_dedupe_seconds <= 0:
            return True

        dedupe_source = ":".join(
            [
                payload.session_id or visitor_key,
                payload.path or "/",
                payload.utm_source or "",
                payload.utm_medium or "",
                payload.utm_campaign or "",
            ]
        )
        dedupe_hash = hashlib.sha256(dedupe_source.encode()).hexdigest()
        stored = await redis.set(
            f"landing:dedupe:{dedupe_hash}",
            "1",
            ex=settings.landing_event_dedupe_seconds,
            nx=True,
        )
        return bool(stored)
    except Exception:
        logger.warning("Landing event Redis guard failed", exc_info=True)
        return payload.event_type == "bot_click"
    finally:
        await redis.aclose()
