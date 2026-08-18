"""SSE sink: bounded queue of request-scoped events.

A slow browser must not grow an unbounded in-memory queue. When the queue is
full, low-priority DEBUG/INFO events are dropped. ERROR, DONE, WARN, and
START events are preserved by dropping an older low-priority item first.

Events are isolated per request — Tenant A cannot observe Tenant B.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from app.observability.events import ObservabilityEvent

HIGH_PRIORITY = {"ERROR", "WARN", "DONE", "START", "HIT", "MISS"}


def encode_sse(event: str, data: dict) -> str:
    payload = json.dumps(data, default=str, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


def encode_heartbeat() -> str:
    return ": heartbeat\n\n"


class SSEEventSink:
    def __init__(self, queue: asyncio.Queue[ObservabilityEvent | None], maxsize: int) -> None:
        self._queue = queue
        self._maxsize = maxsize
        self._dropped = 0

    @property
    def dropped(self) -> int:
        return self._dropped

    async def emit(self, event: ObservabilityEvent) -> None:
        try:
            self._queue.put_nowait(event)
            return
        except asyncio.QueueFull:
            pass

        if event.level in HIGH_PRIORITY or event.event in {"done", "request_completed"}:
            dropped = await self._drop_low_priority()
            if dropped:
                try:
                    self._queue.put_nowait(event)
                    return
                except asyncio.QueueFull:
                    self._dropped += 1
                    return
        self._dropped += 1

    async def _drop_low_priority(self) -> bool:
        buffered: list[ObservabilityEvent | None] = []
        dropped = False
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item is None:
                buffered.append(item)
                continue
            if not dropped and item.level not in HIGH_PRIORITY:
                dropped = True
                self._dropped += 1
                continue
            buffered.append(item)
        for item in buffered:
            try:
                self._queue.put_nowait(item)
            except asyncio.QueueFull:
                break
        return dropped


async def iter_sse_queue(
    queue: asyncio.Queue[ObservabilityEvent | None],
    *,
    heartbeat_seconds: float,
) -> AsyncIterator[str]:
    """Yield framed SSE bytes until a None sentinel is pushed."""
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
        except TimeoutError:
            yield encode_heartbeat()
            continue
        if item is None:
            return
        yield encode_sse("log", item.to_sse_payload())
