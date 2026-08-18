"""Redis-backed sliding-window rate limiter with in-memory fallback.

Rate limiting = operations per unit time.
Concurrency limiting = simultaneous in-flight operations (see concurrency.py).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.exceptions import RateLimitError
from app.observability.events import ObservabilityEvent


class RateLimiter:
    def __init__(
        self,
        redis_client: object | None,
        *,
        per_user_per_minute: int,
        per_tenant_per_minute: int,
    ) -> None:
        self._redis = redis_client
        self.per_user = per_user_per_minute
        self.per_tenant = per_tenant_per_minute
        self._local: dict[str, deque[float]] = defaultdict(deque)

    async def check(self, *, user_id: str, tenant_id: str, request_id: str = "") -> None:
        now = time.time()
        await self._hit(f"user:{user_id}", self.per_user, now, "user", request_id, tenant_id)
        await self._hit(f"tenant:{tenant_id}", self.per_tenant, now, "tenant", request_id, tenant_id)

    async def _hit(
        self,
        key: str,
        limit: int,
        now: float,
        scope: str,
        request_id: str,
        tenant_id: str,
    ) -> None:
        window_start = now - 60
        client = self._redis
        if client is not None and hasattr(client, "zadd"):
            try:
                pipe = client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, 120)
                results = await pipe.execute()
                count = int(results[2])
            except Exception:
                count = self._local_hit(key, now, window_start)
        else:
            count = self._local_hit(key, now, window_start)

        if count > limit:
            raise RateLimitError(f"Rate limit exceeded for {scope}")

    def _local_hit(self, key: str, now: float, window_start: float) -> int:
        bucket = self._local[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        bucket.append(now)
        return len(bucket)


def rate_limit_event(request_id: str, tenant_id: str, scope: str) -> ObservabilityEvent:
    return ObservabilityEvent(
        request_id=request_id,
        level="WARN",
        stage="AUTH",
        event="rate_limited",
        message=f"Rate limit exceeded for {scope}",
        tenant_id=tenant_id,
        metadata={"scope": scope},
    )
