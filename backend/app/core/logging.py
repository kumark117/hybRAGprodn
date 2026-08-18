"""Structured JSON logging with structlog.

Never log JWTs, Authorization headers, API keys, Redis URLs with passwords,
full prompts, or complete document bodies.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

import structlog

from app.core.config import Settings

_SECRET_KEYS = {
    "authorization",
    "password",
    "api_key",
    "apikey",
    "token",
    "jwt",
    "secret",
    "openai_api_key",
    "pinecone_api_key",
    "redis_url",
}
_REDACT = "***REDACTED***"
_BEARER_RE = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


def redact_value(key: str, value: Any) -> Any:
    if key.lower() in _SECRET_KEYS:
        return _REDACT
    if isinstance(value, str):
        return _BEARER_RE.sub("Bearer ***REDACTED***", value)
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    return value


def _redact_event(_: Any, __: Any, event_dict: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in event_dict.items()}


def configure_logging(settings: Settings) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        _redact_event,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.LOG_FORMAT == "console" or settings.is_development and settings.LOG_FORMAT != "json":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.LOG_LEVEL.upper())


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_request_context(
    *,
    request_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> None:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        trace_id=trace_id,
        span_id=span_id,
    )


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
