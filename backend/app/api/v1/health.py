from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.api.dependencies import get_container
from app.container import AppContainer
from app.observability.metrics import render_metrics
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def live(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", request_id=getattr(request.state, "request_id", None))


@router.get("/health/ready", response_model=HealthResponse)
async def ready(request: Request, container: AppContainer = Depends(get_container)) -> HealthResponse:
    checks: dict[str, str] = {}
    try:
        bm25_ok = await container.bm25.ping()
        checks["bm25"] = "ok" if bm25_ok else "fail"
    except Exception:
        checks["bm25"] = "fail"
    try:
        vector_ok = await container.vector_store.ping()
        checks["vector"] = "ok" if vector_ok else "degraded"
    except Exception:
        checks["vector"] = "degraded"
    try:
        if container.redis is not None:
            await container.redis.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "optional_unavailable"
    except Exception:
        checks["redis"] = "optional_unavailable"

    # Readiness: process can serve. Redis is optional when CACHE_FAIL_OPEN.
    status = "ok" if checks.get("bm25") == "ok" else "degraded"
    return HealthResponse(
        status=status,
        request_id=getattr(request.state, "request_id", None),
        checks=checks,
    )


@router.get("/metrics")
async def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)
