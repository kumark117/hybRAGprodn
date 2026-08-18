"""Step timing collector used by RAG and indexing orchestrators."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from app.observability.events import ObservabilityEvent, Stage
from app.observability.event_bus import EventSink


class TimingCollector:
    def __init__(self) -> None:
        self.started = time.perf_counter()
        self.steps: dict[str, float] = {}

    def record(self, name: str, duration_ms: float) -> None:
        self.steps[name] = round(duration_ms, 3)

    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self.started) * 1000, 3)

    def as_dict(self) -> dict[str, float]:
        payload = dict(self.steps)
        payload["total_ms"] = self.elapsed_ms()
        return payload


@contextmanager
def timed_step(collector: TimingCollector, name: str) -> Iterator[None]:
    start = time.perf_counter()
    try:
        yield
    finally:
        collector.record(name, (time.perf_counter() - start) * 1000)


@asynccontextmanager
async def emit_stage(
    sink: EventSink,
    *,
    request_id: str,
    stage: Stage,
    start_event: str,
    ok_event: str,
    start_message: str,
    ok_message: Callable[[float], str] | str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    timing: TimingCollector | None = None,
    timing_key: str | None = None,
    start_level: str = "START",
    metadata: dict[str, Any] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Emit START + OK/ERROR around an awaited block and capture duration."""
    await sink.emit(
        ObservabilityEvent(
            request_id=request_id,
            level=start_level,  # type: ignore[arg-type]
            stage=stage,
            event=start_event,
            message=start_message,
            tenant_id=tenant_id,
            user_id=user_id,
            metadata=metadata or {},
        )
    )
    started = time.perf_counter()
    extra: dict[str, Any] = {}
    try:
        yield extra
        duration_ms = (time.perf_counter() - started) * 1000
        if timing is not None:
            timing.record(timing_key or f"{stage.lower()}_ms", duration_ms)
        message = ok_message(duration_ms) if callable(ok_message) else ok_message
        await sink.emit(
            ObservabilityEvent(
                request_id=request_id,
                level="OK",
                stage=stage,
                event=ok_event,
                message=message,
                duration_ms=duration_ms,
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={**(metadata or {}), **extra},
            )
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - started) * 1000
        if timing is not None:
            timing.record(timing_key or f"{stage.lower()}_ms", duration_ms)
        await sink.emit(
            ObservabilityEvent(
                request_id=request_id,
                level="ERROR",
                stage=stage,
                event=f"{stage.lower()}_failed",
                message=f"{stage} failed: {type(exc).__name__}",
                duration_ms=duration_ms,
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"error_type": type(exc).__name__},
            )
        )
        raise


async def emit_simple(
    sink: EventSink,
    *,
    request_id: str,
    stage: Stage,
    event: str,
    message: str,
    level: str = "INFO",
    duration_ms: float | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    await sink.emit(
        ObservabilityEvent(
            request_id=request_id,
            level=level,  # type: ignore[arg-type]
            stage=stage,
            event=event,
            message=message,
            duration_ms=duration_ms,
            tenant_id=tenant_id,
            user_id=user_id,
            metadata=metadata or {},
        )
    )
