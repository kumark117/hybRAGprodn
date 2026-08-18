"""Request correlation middleware: request_id, tenant-safe context, timings."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import bind_request_context, clear_request_context
from app.observability.events import new_request_id
from app.observability.tracing import current_trace_ids


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = new_request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        request.state.started_at = time.perf_counter()
        trace_id, span_id = current_trace_ids()
        bind_request_context(request_id=request_id, trace_id=trace_id, span_id=span_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers["X-Request-ID"] = request_id
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        return response
