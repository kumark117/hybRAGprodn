from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=128)
    tenant_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    document_version: str = "v1"


class IndexResult(BaseModel):
    request_id: str
    document_id: str
    chunks_created: int
    vectors_indexed: int
    bm25_documents_indexed: int
    status: str
    timings: dict[str, float] = Field(default_factory=dict)


class IndexStatus(BaseModel):
    document_id: str
    tenant_id: str
    status: str
    chunks_created: int = 0
    updated_at: str | None = None
    error: str | None = None


class BatchIndexRequest(BaseModel):
    documents: list[IndexRequest] = Field(min_length=1, max_length=50)
