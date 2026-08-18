"""Concurrency limiting via asyncio.Semaphore.

Rate limiting caps requests over time.
Concurrency limiting caps how many expensive calls run at once (LLM, embed, rerank).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from prometheus_client import Gauge

LLM_INFLIGHT = Gauge("rag_active_llm_requests", "In-flight LLM generations")
EMBED_INFLIGHT = Gauge("rag_active_embedding_requests", "In-flight embedding calls")
RERANK_INFLIGHT = Gauge("rag_active_rerank_requests", "In-flight rerank calls")
QUERY_INFLIGHT = Gauge("rag_active_query_requests", "In-flight RAG queries")


class ConcurrencyLimiter:
    def __init__(self, llm: int, embedding: int, rerank: int) -> None:
        self.llm = asyncio.Semaphore(llm)
        self.embedding = asyncio.Semaphore(embedding)
        self.rerank = asyncio.Semaphore(rerank)
        self.query = asyncio.Semaphore(max(llm, 16))

    @asynccontextmanager
    async def limit_llm(self) -> AsyncIterator[None]:
        async with self.llm:
            LLM_INFLIGHT.inc()
            try:
                yield
            finally:
                LLM_INFLIGHT.dec()

    @asynccontextmanager
    async def limit_embedding(self) -> AsyncIterator[None]:
        async with self.embedding:
            EMBED_INFLIGHT.inc()
            try:
                yield
            finally:
                EMBED_INFLIGHT.dec()

    @asynccontextmanager
    async def limit_rerank(self) -> AsyncIterator[None]:
        async with self.rerank:
            RERANK_INFLIGHT.inc()
            try:
                yield
            finally:
                RERANK_INFLIGHT.dec()

    @asynccontextmanager
    async def limit_query(self) -> AsyncIterator[None]:
        async with self.query:
            QUERY_INFLIGHT.inc()
            try:
                yield
            finally:
                QUERY_INFLIGHT.dec()
