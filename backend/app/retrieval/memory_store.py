"""In-memory dense vector store used for local development and tests."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from app.models.document import Chunk, RetrievedChunk


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._vectors: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()

    async def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        async with self._lock:
            for chunk, vector in zip(chunks, embeddings, strict=True):
                self._chunks[chunk.chunk_id] = chunk
                self._vectors[chunk.chunk_id] = _normalize(np.array(vector, dtype=np.float32))
            return len(chunks)

    async def search(
        self,
        embedding: list[float],
        *,
        tenant_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        query = _normalize(np.array(embedding, dtype=np.float32))
        scored: list[tuple[float, str]] = []
        async with self._lock:
            items = list(self._chunks.items())
            vectors = dict(self._vectors)
        for chunk_id, chunk in items:
            if chunk.tenant_id != tenant_id:
                continue
            if filters:
                skip = False
                for key, value in filters.items():
                    if key == "tenant_id":
                        continue
                    if chunk.metadata.get(key) != value and (
                        key != "source" or chunk.source != value
                    ):
                        if key == "source" and chunk.source != value:
                            skip = True
                        elif key != "source":
                            skip = True
                if skip:
                    continue
            vector = vectors.get(chunk_id)
            if vector is None:
                continue
            score = float(np.dot(query, vector))
            scored.append((score, chunk_id))
        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[RetrievedChunk] = []
        for rank, (score, chunk_id) in enumerate(scored[:top_k], start=1):
            results.append(
                RetrievedChunk(
                    chunk=self._chunks[chunk_id],
                    retrieval_score=score,
                    vector_rank=rank,
                    origin="vector",
                )
            )
        return results

    async def delete_document(self, tenant_id: str, document_id: str) -> int:
        async with self._lock:
            to_delete = [
                cid
                for cid, chunk in self._chunks.items()
                if chunk.tenant_id == tenant_id and chunk.document_id == document_id
            ]
            for cid in to_delete:
                self._chunks.pop(cid, None)
                self._vectors.pop(cid, None)
            return len(to_delete)

    async def ping(self) -> bool:
        return True


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm
