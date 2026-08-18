"""Query APIs — JSON and one SSE connection for logs, tokens, citations, done."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_container, get_principal, require_tenant
from app.container import AppContainer
from app.core.security import Principal
from app.observability.event_bus import CompositeEventSink
from app.observability.events import ObservabilityEvent
from app.observability.sse_sink import encode_heartbeat, encode_sse
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class OutboundSink:
    """Request-scoped sink that writes typed SSE frames onto a bounded queue."""

    def __init__(self, queue: asyncio.Queue[tuple[str, dict[str, Any]] | None]) -> None:
        self._queue = queue

    async def emit(self, event: ObservabilityEvent) -> None:
        frame = ("log", event.to_sse_payload())
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            if event.level in {"ERROR", "WARN", "DONE", "START"}:
                try:
                    _ = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    self._queue.put_nowait(frame)
                except asyncio.QueueFull:
                    return


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    container: AppContainer = Depends(get_container),
) -> QueryResponse:
    require_tenant(body.tenant_id, principal)
    return await container.rag.query(
        body,
        principal,
        container.base_sink(),
        request_id=request.state.request_id,
        stream=False,
    )


@router.post("/stream")
async def query_stream(
    body: QueryRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    require_tenant(body.tenant_id, principal)
    request_id = request.state.request_id
    outbound: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue(
        maxsize=container.settings.SSE_QUEUE_MAX_SIZE
    )
    sse_sink = OutboundSink(outbound)
    sink = CompositeEventSink([container.log_sink, container.metrics_sink, sse_sink])
    cancelled = {"value": False}

    async def on_token(text: str) -> None:
        frame = ("token", {"request_id": request_id, "text": text})
        try:
            outbound.put_nowait(frame)
        except asyncio.QueueFull:
            await outbound.put(frame)

    async def run() -> None:
        try:
            result = await container.rag.query(
                body,
                principal,
                sink,
                request_id=request_id,
                stream=True,
                on_token=on_token,
                cancel=lambda: cancelled["value"],
            )
            payload = result.model_dump(mode="json")
            for source in payload.get("sources") or []:
                await outbound.put(("citation", {"request_id": request_id, **source}))
            await outbound.put(
                ("metadata", {"request_id": request_id, "metadata": payload.get("metadata") or {}})
            )
            meta = payload.get("metadata") or {}
            await outbound.put(
                (
                    "done",
                    {
                        "request_id": request_id,
                        "latency_ms": meta.get("latency_ms", 0),
                        "retrieval_mode": meta.get("retrieval_mode", "hybrid"),
                        "cache_hit": meta.get("cache_hit", False),
                        "answer": payload.get("answer") or "",
                    },
                )
            )
        except Exception as exc:
            await outbound.put(
                (
                    "error",
                    {
                        "request_id": request_id,
                        "code": getattr(exc, "code", "QUERY_FAILED"),
                        "message": "Query failed",
                    },
                )
            )
            await outbound.put(
                ("done", {"request_id": request_id, "latency_ms": 0, "retrieval_mode": "none"})
            )
        finally:
            await outbound.put(None)

    task = asyncio.create_task(run())

    async def event_stream():
        heartbeat = container.settings.SSE_HEARTBEAT_SECONDS
        try:
            while True:
                if await request.is_disconnected():
                    cancelled["value"] = True
                    task.cancel()
                    break
                try:
                    item = await asyncio.wait_for(outbound.get(), timeout=heartbeat)
                except TimeoutError:
                    yield encode_heartbeat()
                    continue
                if item is None:
                    break
                event_name, data = item
                yield encode_sse(event_name, data)
                if event_name == "done":
                    break
        finally:
            cancelled["value"] = True
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Request-ID": request_id,
        },
    )
