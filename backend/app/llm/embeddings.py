"""Embedding providers: OpenAI and a local hashing fake for tests."""

from __future__ import annotations

import asyncio
import hashlib
import math

from openai import AsyncOpenAI

from app.core.config import Settings
from app.core.retry import classify_http_status, retry_async
from app.llm.base import EmbeddingProvider


class OpenAIEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY or "missing",
            base_url=settings.OPENAI_BASE_URL,
            timeout=settings.EMBEDDING_TIMEOUT_SECONDS,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async def _call() -> list[list[float]]:
            try:
                response = await self._client.embeddings.create(model=self.model, input=texts)
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status:
                    raise classify_http_status(int(status), "embedding", "embedding failed") from exc
                raise
            return [item.embedding for item in response.data]

        return await retry_async(
            _call,
            max_attempts=self._settings.MAX_RETRIES,
            timeout_seconds=self._settings.EMBEDDING_TIMEOUT_SECONDS,
            provider="embedding",
            operation_name="embed",
        )


class HashEmbeddingProvider:
    """Deterministic pseudo-embeddings so tests never call a paid API."""

    def __init__(self, dimension: int = 64) -> None:
        self.model = "hash-embed-v1"
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        await asyncio.sleep(0)
        return [_hash_vector(text, self.dimension) for text in texts]


def _hash_vector(text: str, dimension: int) -> list[float]:
    vec = [0.0] * dimension
    tokens = text.lower().split() or [text]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for i in range(0, min(len(digest), dimension)):
            vec[i % dimension] += ((digest[i] / 255.0) * 2) - 1
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
