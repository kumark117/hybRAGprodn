from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LogEvent(BaseModel):
    request_id: str
    timestamp: str
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "START", "OK", "MISS", "HIT", "DONE"]
    stage: str
    event: str
    message: str
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TokenEvent(BaseModel):
    request_id: str
    text: str


class CitationEvent(BaseModel):
    request_id: str
    sources: list[dict[str, Any]]


class MetadataEvent(BaseModel):
    request_id: str
    metadata: dict[str, Any]


class ErrorEvent(BaseModel):
    request_id: str
    code: str
    message: str


class DoneEvent(BaseModel):
    request_id: str
    latency_ms: float
    retrieval_mode: str
    cache_hit: bool = False
