from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1, max_length=64)
    top_k: int = Field(default=12, ge=1, le=20)
    filters: dict[str, Any] = Field(default_factory=dict)
    use_cache: bool = True
    debug: bool = False
    rewrite: bool | None = None


class Source(BaseModel):
    citation_id: int
    document_id: str
    chunk_id: str
    source: str
    retrieval_score: float | None = None
    rrf_score: float | None = None
    reranker_score: float | None = None
    text_preview: str | None = None


class RAGMetadata(BaseModel):
    cache_hit: bool = False
    fallback_used: bool = False
    degraded_mode: bool = False
    retrieval_mode: Literal["hybrid", "vector_only", "bm25_only", "none"] = "hybrid"
    candidate_count: int = 0
    context_chunk_count: int = 0
    time_to_first_token_ms: float | None = None
    latency_ms: float = 0
    llm_model: str | None = None
    rewritten_query: str | None = None
    timings: dict[str, float] = Field(default_factory=dict)
    retry_count: int = 0
    trace_id: str | None = None


class DebugPayload(BaseModel):
    original_query: str | None = None
    rewritten_query: str | None = None
    vector_candidates: list[dict[str, Any]] = Field(default_factory=list)
    bm25_candidates: list[dict[str, Any]] = Field(default_factory=list)
    rrf_results: list[dict[str, Any]] = Field(default_factory=list)
    reranked: list[dict[str, Any]] = Field(default_factory=list)
    context_chunks: list[dict[str, Any]] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)
    cache_hit: bool = False
    fallback_used: bool = False
    retrieval_mode: str | None = None


class QueryResponse(BaseModel):
    request_id: str
    trace_id: str | None = None
    answer: str
    sources: list[Source] = Field(default_factory=list)
    metadata: RAGMetadata
    debug: DebugPayload | None = None
