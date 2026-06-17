from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic

from redis.asyncio import Redis

from kcal_tracker.config import settings

logger = logging.getLogger(__name__)


class AIPhotoQueueFullError(RuntimeError):
    pass


@asynccontextmanager
async def ai_photo_slot(owner: str | int) -> AsyncIterator[float]:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    token = secrets.token_hex(8)
    deadline = monotonic() + settings.ai_photo_queue_wait_seconds
    slot_key: str | None = None
    waited = 0.0
    try:
        while True:
            slot_key = await _try_acquire_slot(redis, token, owner)
            if slot_key is not None:
                waited = max(0.0, settings.ai_photo_queue_wait_seconds - (deadline - monotonic()))
                break
            if monotonic() >= deadline:
                raise AIPhotoQueueFullError("AI photo queue is full")
            await asyncio.sleep(0.25)
        yield waited
    except Exception:
        raise
    finally:
        if slot_key is not None:
            try:
                current = await redis.get(slot_key)
                if current == token:
                    await redis.delete(slot_key)
            except Exception:
                logger.warning("Failed to release AI photo queue slot", exc_info=True)
        await redis.aclose()


async def _try_acquire_slot(redis: Redis, token: str, owner: str | int) -> str | None:
    for index in range(settings.ai_photo_queue_concurrency):
        key = f"ai:photo:slot:{index}"
        acquired = await redis.set(
            key,
            token,
            ex=settings.ai_photo_queue_slot_ttl_seconds,
            nx=True,
        )
        if acquired:
            logger.info("Acquired AI photo slot index=%s owner=%s", index, owner)
            return key
    return None
