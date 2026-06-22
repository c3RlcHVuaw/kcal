from __future__ import annotations

import logging

from redis.asyncio import Redis
from sqlalchemy import text

from kcal_tracker.config import settings
from kcal_tracker.database import engine

logger = logging.getLogger(__name__)


async def check_database() -> bool:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    except Exception:
        logger.exception("Readiness database check failed")
        return False
    return True


async def check_redis() -> bool:
    redis = Redis.from_url(settings.redis_url)
    try:
        return bool(await redis.ping())
    except Exception:
        logger.exception("Readiness Redis check failed")
        return False
    finally:
        await redis.aclose()
