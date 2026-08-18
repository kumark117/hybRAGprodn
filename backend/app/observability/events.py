"""Observability event model shared by logs, SSE, metrics, and traces."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

LogLevel = Literal["DEBUG", "INFO", "WARN", "ERROR", "START", "OK", "MISS", "HIT", "DONE"]

Stage = Literal[
    "REQUEST",
    "AUTH",
    "VALIDATION",
    "CACHE",
    "REWRITE",
    "EMBED",
    "VECTOR",
    "BM25",
    "RRF",
    "DEDUP",
    "RERANK",
    "CONTEXT",
    "PROMPT",
    "LLM",
    "RETRY",
    "FAILOVER",
    "INDEX",
    "COMPLETE",
    "MODE",
    "RETRIEVAL",
]


class ObservabilityEvent(BaseModel):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    level: LogLevel = "INFO"
    stage: Stage | str = "REQUEST"
    event: str
    message: str
    duration_ms: float | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_log_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "event": self.event,
            "stage": self.stage,
            "request_id": self.request_id,
            "message": self.message,
        }
        if self.duration_ms is not None:
            payload["duration_ms"] = round(self.duration_ms, 3)
        if self.tenant_id:
            payload["tenant_id"] = self.tenant_id
        if self.user_id:
            payload["user_id"] = self.user_id
        if self.trace_id:
            payload["trace_id"] = self.trace_id
        if self.span_id:
            payload["span_id"] = self.span_id
        for key, value in self.metadata.items():
            if key not in payload:
                payload[key] = value
        return payload

    def to_sse_payload(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "stage": self.stage,
            "event": self.event,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


def new_request_id(provided: str | None = None) -> str:
    if provided and 8 <= len(provided) <= 64 and provided.replace("-", "").isalnum():
        return provided
    return f"req-{uuid4().hex[:12]}"
