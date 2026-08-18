"""Event bus: one pipeline event fans out to logs, SSE, and metrics.

                    Pipeline Event
                         |
              +----------+----------+
              |          |          |
              v          v          v
            Logs       SSE UI     Metrics/Trace
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.observability.events import ObservabilityEvent


@runtime_checkable
class EventSink(Protocol):
    async def emit(self, event: ObservabilityEvent) -> None: ...


class NullEventSink:
    async def emit(self, event: ObservabilityEvent) -> None:
        return None


class CompositeEventSink:
    """Fan a single event out to many sinks. Failures in one sink do not stop others."""

    def __init__(self, sinks: list[EventSink]) -> None:
        self._sinks = sinks

    async def emit(self, event: ObservabilityEvent) -> None:
        for sink in self._sinks:
            try:
                await sink.emit(event)
            except Exception:
                continue

    def add(self, sink: EventSink) -> None:
        self._sinks.append(sink)
