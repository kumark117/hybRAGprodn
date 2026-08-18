"""Reranking: bi-encoder retrieval is cheap; a cross-encoder is precise.

Retrieval (bi-encoder): encode query and documents separately, compare vectors.
Reranking (cross-encoder): score (query, document) pairs jointly.

A hosted Cohere/Jina reranker can replace LocalCrossEncoderReranker by
implementing the same Reranker protocol.
"""

from __future__ import annotations

import asyncio
import math
import re
from typing import Protocol, runtime_checkable

from app.models.document import RetrievedChunk

_TOKEN = re.compile(r"[a-z0-9]+")


@runtime_checkable
class Reranker(Protocol):
    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        *,
        top_k: int,
    ) -> list[RetrievedChunk]: ...


class LexicalOverlapReranker:
    """Always-available fallback. Uses overlap + BM25/RRF hints.

    Used in tests and when sentence-transformers is not installed.
    """

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        q = set(_TOKEN.findall(query.lower()))
        scored: list[RetrievedChunk] = []
        for item in candidates:
            haystack = f"{item.chunk.source} {item.chunk.document_id} {item.chunk.text}"
            d = set(_TOKEN.findall(haystack.lower()))
            overlap = len(q & d) / max(1, len(q))
            rrf = item.rrf_score or 0.0
            score = 0.7 * overlap + 0.3 * min(1.0, rrf * 40)
            clone = item.model_copy(deep=True)
            clone.reranker_score = float(score)
            scored.append(clone)
        scored.sort(key=lambda x: x.reranker_score or 0.0, reverse=True)
        return scored[:top_k]


class LocalCrossEncoderReranker:
    """sentence-transformers CrossEncoder, loaded lazily."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self.model_name = model_name
        self._model = None
        self._lock = asyncio.Lock()

    async def _load(self):
        if self._model is not None:
            return self._model
        async with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder

                self._model = await asyncio.to_thread(CrossEncoder, self.model_name)
        return self._model

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        *,
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        model = await self._load()
        pairs = [(query, item.chunk.text) for item in candidates]
        scores = await asyncio.to_thread(model.predict, pairs)
        ranked: list[RetrievedChunk] = []
        for item, score in zip(candidates, scores, strict=True):
            clone = item.model_copy(deep=True)
            clone.reranker_score = float(score)
            ranked.append(clone)
        ranked.sort(key=lambda x: x.reranker_score or 0.0, reverse=True)
        return ranked[:top_k]


def softmax(values: list[float]) -> list[float]:
    peak = max(values) if values else 0.0
    exps = [math.exp(v - peak) for v in values]
    total = sum(exps) or 1.0
    return [e / total for e in exps]
