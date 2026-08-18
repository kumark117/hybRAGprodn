"""Indexing APIs — sync and SSE streaming."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_container, get_principal, require_tenant
from app.container import AppContainer
from app.core.exceptions import NotFoundError
from app.core.security import Principal
from app.observability.event_bus import CompositeEventSink
from app.observability.sse_sink import SSEEventSink, encode_heartbeat, encode_sse
from app.schemas.index import BatchIndexRequest, IndexRequest, IndexResult, IndexStatus

router = APIRouter(prefix="/api/v1/index", tags=["index"])


@router.post("", response_model=IndexResult)
async def index_document(
    body: IndexRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    container: AppContainer = Depends(get_container),
) -> IndexResult:
    require_tenant(body.tenant_id, principal)
    request_id = request.state.request_id
    return await container.indexing.index_document(
        body,
        request_id=request_id,
        tenant_id=principal.tenant_id,
        sink=container.base_sink(),
        user_id=principal.user_id,
    )


@router.post("/batch", response_model=list[IndexResult])
async def index_batch(
    body: BatchIndexRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    container: AppContainer = Depends(get_container),
) -> list[IndexResult]:
    results: list[IndexResult] = []
    for doc in body.documents:
        require_tenant(doc.tenant_id, principal)
        results.append(
            await container.indexing.index_document(
                doc,
                request_id=request.state.request_id,
                tenant_id=principal.tenant_id,
                sink=container.base_sink(),
                user_id=principal.user_id,
            )
        )
    return results


@router.post("/stream")
async def index_stream(
    body: IndexRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    container: AppContainer = Depends(get_container),
) -> StreamingResponse:
    require_tenant(body.tenant_id, principal)
    request_id = request.state.request_id
    queue: asyncio.Queue = asyncio.Queue(maxsize=container.settings.SSE_QUEUE_MAX_SIZE)
    sse_sink = SSEEventSink(queue, container.settings.SSE_QUEUE_MAX_SIZE)
    sink = CompositeEventSink([container.log_sink, container.metrics_sink, sse_sink])

    async def run() -> None:
        try:
            result = await container.indexing.index_document(
                body,
                request_id=request_id,
                tenant_id=principal.tenant_id,
                sink=sink,
                user_id=principal.user_id,
            )
            payload = result.model_dump(mode="json")
            await queue.put(("__done__", payload))
        except Exception as exc:
            await queue.put(
                ("__error__", {"code": getattr(exc, "code", "INDEX_FAILED"), "message": "Indexing failed"})
            )

    task = asyncio.create_task(run())

    async def event_stream():
        heartbeat = container.settings.SSE_HEARTBEAT_SECONDS
        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=heartbeat)
                except TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield encode_heartbeat()
                    continue
                if isinstance(item, tuple) and item[0] == "__done__":
                    done = item[1]
                    yield encode_sse("metadata", {"request_id": request_id, "metadata": done})
                    yield encode_sse(
                        "done",
                        {
                            "request_id": request_id,
                            "latency_ms": (done.get("timings") or {}).get("total_ms", 0),
                            "retrieval_mode": "index",
                        },
                    )
                    break
                if isinstance(item, tuple) and item[0] == "__error__":
                    yield encode_sse("error", {"request_id": request_id, **item[1]})
                    yield encode_sse("done", {"request_id": request_id, "latency_ms": 0, "retrieval_mode": "index"})
                    break
                yield encode_sse("log", item.to_sse_payload())
        finally:
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


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    principal: Principal = Depends(get_principal),
    container: AppContainer = Depends(get_container),
) -> dict:
    await container.indexing.delete(principal.tenant_id, document_id)
    return {"status": "deleted", "document_id": document_id}


@router.get("/{document_id}/status", response_model=IndexStatus)
async def document_status(
    document_id: str,
    principal: Principal = Depends(get_principal),
    container: AppContainer = Depends(get_container),
) -> IndexStatus:
    status = container.indexing.get_status(principal.tenant_id, document_id)
    if status is None:
        raise NotFoundError("Document not indexed", code="DOCUMENT_NOT_FOUND")
    return status
