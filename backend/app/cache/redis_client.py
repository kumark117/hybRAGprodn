"""Redis client factory with fail-open fallback."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger("rag.redis")


async def create_redis(settings: Settings):
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(
            settings.REDIS_URL,
            socket_timeout=settings.REDIS_TIMEOUT_SECONDS,
            socket_connect_timeout=settings.REDIS_TIMEOUT_SECONDS,
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception as exc:
        logger.warning("redis_unavailable", error=type(exc).__name__)
        return None
