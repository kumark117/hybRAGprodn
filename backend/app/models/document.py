"""Domain models for chunks and retrieval candidates."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str
    tenant_id: str
    document_id: str
    document_version: str
    chunk_index: int
    source: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    token_count: int = 0


class RetrievedChunk(BaseModel):
    chunk: Chunk
    retrieval_score: float | None = None
    vector_rank: int | None = None
    bm25_rank: int | None = None
    rrf_score: float | None = None
    reranker_score: float | None = None
    origin: str = "unknown"

    @property
    def chunk_id(self) -> str:
        return self.chunk.chunk_id

    def debug_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk.chunk_id,
            "document_id": self.chunk.document_id,
            "source": self.chunk.source,
            "vector_rank": self.vector_rank,
            "bm25_rank": self.bm25_rank,
            "rrf_score": self.rrf_score,
            "reranker_score": self.reranker_score,
            "retrieval_score": self.retrieval_score,
            "preview": self.chunk.text[:180],
        }
