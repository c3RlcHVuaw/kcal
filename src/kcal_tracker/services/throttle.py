from __future__ import annotations

import logging

from redis.asyncio import Redis

from kcal_tracker.config import settings

logger = logging.getLogger(__name__)


class ThrottleLimitReached(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many requests")
        self.retry_after_seconds = max(retry_after_seconds, 1)


async def ensure_rate_limit(
    key: str,
    *,
    limit: int,
    window_seconds: int = 60,
) -> None:
    if limit <= 0:
        return
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count <= limit:
            return
        ttl = await redis.ttl(key)
        raise ThrottleLimitReached(ttl if ttl and ttl > 0 else window_seconds)
    except ThrottleLimitReached:
        raise
    except Exception:
        logger.warning("Rate limit check failed key=%s", key, exc_info=True)
    finally:
        await redis.aclose()


async def ensure_ai_rate_limit(user_key: str | int, action: str) -> None:
    await ensure_rate_limit(
        f"ai:user:{user_key}",
        limit=settings.ai_burst_per_user_per_minute,
        window_seconds=60,
    )
    await ensure_rate_limit(
        f"ai:global:{action}",
        limit=settings.ai_global_burst_per_minute,
        window_seconds=60,
    )


async def ensure_barcode_rate_limit(user_key: str | int) -> None:
    await ensure_rate_limit(
        f"barcode:user:{user_key}",
        limit=settings.barcode_burst_per_user_per_minute,
        window_seconds=60,
    )


async def reserve_auto_message(
    user_key: str | int,
    message_type: str,
    *,
    window_seconds: int = 23 * 60 * 60,
) -> bool:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    key = f"auto-message:{message_type}:{user_key}"
    try:
        return bool(await redis.set(key, "1", ex=window_seconds, nx=True))
    except Exception:
        logger.warning("Auto-message guard failed key=%s", key, exc_info=True)
        return True
    finally:
        await redis.aclose()
