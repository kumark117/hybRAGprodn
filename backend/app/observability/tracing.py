"""OpenTelemetry tracing. Safe attributes only — no prompts, docs, or secrets.

The app still runs if OTEL is disabled or no collector is listening.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode, Tracer

from app.core.config import Settings

_tracer: Tracer | None = None
_provider: TracerProvider | None = None


def configure_tracing(settings: Settings) -> None:
    global _tracer, _provider
    if not settings.OTEL_ENABLED:
        _tracer = trace.get_tracer(settings.OTEL_SERVICE_NAME)
        return

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "deployment.environment": settings.APP_ENV,
        }
    )
    provider = TracerProvider(resource=resource)
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=f"{settings.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _provider = provider
    _tracer = trace.get_tracer(settings.OTEL_SERVICE_NAME)


def get_tracer() -> Tracer:
    return _tracer or trace.get_tracer("rag-backend")


def current_trace_ids() -> tuple[str | None, str | None]:
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.trace_id:
        return None, None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


@contextmanager
def stage_span(name: str, **attributes: Any) -> Iterator[Span]:
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is None:
                continue
            if key in {"prompt", "document", "text", "query", "api_key", "authorization"}:
                continue
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            raise


def shutdown_tracing() -> None:
    if _provider is not None:
        _provider.shutdown()
