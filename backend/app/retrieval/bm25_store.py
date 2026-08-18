"""In-process BM25 lexical store.

This is excellent for learning and single-process demos. It is NOT
automatically consistent across FastAPI replicas. Horizontally scaled
production should swap this for OpenSearch/Elasticsearch via the same
LexicalStore protocol.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections import defaultdict
from typing import Any, Protocol, runtime_checkable

from rank_bm25 import BM25Okapi

from app.models.document import Chunk, RetrievedChunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def chunk_search_text(chunk: Chunk) -> str:
    """BM25/overlap text includes path tokens so 'interview notes' hits interview-notes.md."""
    return f"{chunk.source} {chunk.document_id} {chunk.text}"


@runtime_checkable
class LexicalStore(Protocol):
    async def upsert(self, chunks: list[Chunk]) -> int: ...

    async def search(
        self,
        query: str,
        *,
        tenant_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]: ...

    async def delete_document(self, tenant_id: str, document_id: str) -> int: ...

    async def ping(self) -> bool: ...


class BM25Store:
    """Tenant-isolated in-memory BM25 index rebuilt on mutation.

    Tenant isolation happens at search time: only that tenant's corpus is
    scored. Unauthorized chunks never enter the ranked list.
    """

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._by_tenant: dict[str, list[str]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._indexes: dict[str, tuple[BM25Okapi, list[str]]] = {}

    async def upsert(self, chunks: list[Chunk]) -> int:
        async with self._lock:
            tenants: set[str] = set()
            for chunk in chunks:
                previous = self._chunks.get(chunk.chunk_id)
                if previous and previous.tenant_id != chunk.tenant_id:
                    continue
                self._chunks[chunk.chunk_id] = chunk
                if chunk.chunk_id not in self._by_tenant[chunk.tenant_id]:
                    self._by_tenant[chunk.tenant_id].append(chunk.chunk_id)
                tenants.add(chunk.tenant_id)
            for tenant in tenants:
                self._rebuild(tenant)
            return len(chunks)

    async def search(
        self,
        query: str,
        *,
        tenant_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        tokens = tokenize(query)
        if not tokens:
            return []
        async with self._lock:
            packed = self._indexes.get(tenant_id)
            if packed is None:
                return []
            bm25, ids = packed
            scores = bm25.get_scores(tokens)
            ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)

        results: list[RetrievedChunk] = []
        rank = 0
        for idx, score in ranked:
            chunk = self._chunks.get(ids[idx])
            if chunk is None or chunk.tenant_id != tenant_id:
                continue
            if filters and not _matches_filters(chunk, filters):
                continue
            rank += 1
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    retrieval_score=float(score),
                    bm25_rank=rank,
                    origin="bm25",
                )
            )
            if rank >= top_k:
                break
        return results

    async def delete_document(self, tenant_id: str, document_id: str) -> int:
        async with self._lock:
            ids = list(self._by_tenant.get(tenant_id, []))
            removed = 0
            remaining: list[str] = []
            for chunk_id in ids:
                chunk = self._chunks.get(chunk_id)
                if chunk and chunk.document_id == document_id:
                    self._chunks.pop(chunk_id, None)
                    removed += 1
                else:
                    remaining.append(chunk_id)
            self._by_tenant[tenant_id] = remaining
            self._rebuild(tenant_id)
            return removed

    async def ping(self) -> bool:
        return True

    def _rebuild(self, tenant_id: str) -> None:
        ids = [cid for cid in self._by_tenant.get(tenant_id, []) if cid in self._chunks]
        corpus = [tokenize(chunk_search_text(self._chunks[cid])) for cid in ids]
        if not corpus:
            self._indexes.pop(tenant_id, None)
            return
        self._indexes[tenant_id] = (BM25Okapi(corpus), ids)


def _matches_filters(chunk: Chunk, filters: dict[str, Any]) -> bool:
    for key, value in filters.items():
        if key == "tenant_id":
            continue
        if chunk.metadata.get(key) != value and getattr(chunk, key, None) != value:
            if key == "source" and chunk.source != value:
                return False
            if key != "source" and chunk.metadata.get(key) != value:
                return False
    return True


def bm25_idf_explain(n_docs: int, df: int) -> float:
    """Visible IDF used by Okapi BM25 — useful in interview notes."""
    return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
