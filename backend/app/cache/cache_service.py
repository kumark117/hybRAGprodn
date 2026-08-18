"""Exact, embedding, and optional semantic caches.

Cache keys always include tenant_id. Entries never leak across tenants.
Redis failure degrades to in-memory or no-cache depending on CACHE_FAIL_OPEN.
"""

from __future__ import annotations

import json
import math
import time
from typing import Any, Protocol, runtime_checkable

from app.cache.keys import embedding_key, exact_query_key, semantic_cache_index_key
from app.core.config import Settings
from app.observability.event_bus import EventSink
from app.observability.timing import emit_simple


@runtime_checkable
class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class InMemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    async def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if not item:
            return None
        expires, value = item
        if expires < time.time():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = (time.time() + ttl_seconds, value)

    async def ping(self) -> bool:
        return True


class RedisCache:
    def __init__(self, client) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        value = await self._client.get(key)
        return value if value is None or isinstance(value, str) else value.decode()

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._client.set(key, value, ex=ttl_seconds)

    async def ping(self) -> bool:
        await self._client.ping()
        return True


class CacheService:
    def __init__(
        self,
        backend: Cache,
        settings: Settings,
        *,
        fail_open: bool = True,
        redis_client: Any | None = None,
    ) -> None:
        self.backend = backend
        self.settings = settings
        self.fail_open = fail_open
        self._redis = redis_client
        self.available = True

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self.backend.get(key)
            self.available = True
            return json.loads(raw) if raw else None
        except Exception:
            self.available = False
            if self.fail_open:
                return None
            raise

    async def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            await self.backend.set(key, json.dumps(value), ttl or self.settings.CACHE_TTL_SECONDS)
            self.available = True
        except Exception:
            self.available = False
            if not self.fail_open:
                raise

    async def embedding_lookup(self, text: str) -> list[float] | None:
        key = embedding_key(text, self.settings.OPENAI_EMBEDDING_MODEL, self.settings.EMBEDDING_MODEL_VERSION)
        value = await self.get_json(key)
        if isinstance(value, list):
            return [float(x) for x in value]
        return None

    async def embedding_store(self, text: str, vector: list[float]) -> None:
        key = embedding_key(text, self.settings.OPENAI_EMBEDDING_MODEL, self.settings.EMBEDDING_MODEL_VERSION)
        await self.set_json(key, vector)

    def exact_key(self, *, tenant_id: str, query: str, filters: dict, llm_model: str) -> str:
        normalized = " ".join(query.lower().split())
        cfg = f"v{self.settings.VECTOR_TOP_K}-b{self.settings.BM25_TOP_K}-r{self.settings.RERANK_TOP_K}"
        return exact_query_key(
            tenant_id=tenant_id,
            normalized_query=normalized,
            filters=filters,
            llm_model=llm_model,
            embedding_model=self.settings.OPENAI_EMBEDDING_MODEL,
            prompt_version=self.settings.PROMPT_VERSION,
            index_version=self.settings.INDEX_VERSION,
            retrieval_config=cfg,
        )

    async def lookup_exact(
        self,
        *,
        key: str,
        sink: EventSink,
        request_id: str,
        tenant_id: str,
    ) -> dict | None:
        await emit_simple(
            sink,
            request_id=request_id,
            stage="CACHE",
            event="cache_lookup_started",
            message="Checking exact cache",
            tenant_id=tenant_id,
        )
        if not self.available and not self.fail_open:
            await emit_simple(
                sink,
                request_id=request_id,
                stage="CACHE",
                event="cache_unavailable",
                message="Cache unavailable",
                level="WARN",
                tenant_id=tenant_id,
            )
            return None
        hit = await self.get_json(key)
        if hit:
            await emit_simple(
                sink,
                request_id=request_id,
                stage="CACHE",
                event="cache_hit",
                message="Cache hit",
                level="HIT",
                tenant_id=tenant_id,
                metadata={"cache_type": "exact"},
            )
            return hit
        await emit_simple(
            sink,
            request_id=request_id,
            stage="CACHE",
            event="cache_miss",
            message="Cache miss",
            level="MISS",
            tenant_id=tenant_id,
            metadata={"cache_type": "exact"},
        )
        return None

    async def write_exact(
        self,
        *,
        key: str,
        payload: dict,
        sink: EventSink,
        request_id: str,
        tenant_id: str,
    ) -> None:
        await emit_simple(
            sink,
            request_id=request_id,
            stage="CACHE",
            event="cache_write_started",
            message="Writing response cache",
            tenant_id=tenant_id,
        )
        await self.set_json(key, payload)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="CACHE",
            event="cache_write_completed",
            message="Response cached",
            level="OK",
            tenant_id=tenant_id,
        )

    async def semantic_lookup(
        self,
        *,
        tenant_id: str,
        query_embedding: list[float],
        sink: EventSink,
        request_id: str,
    ) -> dict | None:
        if not self.settings.SEMANTIC_CACHE_ENABLED:
            return None
        index_key = semantic_cache_index_key(tenant_id)
        entries = await self.get_json(index_key) or []
        best: tuple[float, dict] | None = None
        for entry in entries:
            sim = _cosine(query_embedding, entry.get("embedding") or [])
            if sim >= self.settings.SEMANTIC_CACHE_THRESHOLD and (best is None or sim > best[0]):
                cached = await self.get_json(entry["key"])
                if cached:
                    best = (sim, cached)
        if best:
            await emit_simple(
                sink,
                request_id=request_id,
                stage="CACHE",
                event="cache_hit",
                message=f"Semantic cache hit ({best[0]:.3f})",
                level="HIT",
                tenant_id=tenant_id,
                metadata={"cache_type": "semantic", "similarity": best[0]},
            )
            return best[1]
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
