"""Structured log sink — production logs, not the browser Log Pane."""

from __future__ import annotations

from app.core.logging import get_logger
from app.observability.events import ObservabilityEvent

logger = get_logger("rag.pipeline")


class StructuredLogSink:
    async def emit(self, event: ObservabilityEvent) -> None:
        payload = event.to_log_dict()
        level = event.level
        log = logger.bind(**{k: v for k, v in payload.items() if k != "message"})
        if level in {"ERROR"}:
            log.error(event.message)
        elif level in {"WARN"}:
            log.warning(event.message)
        elif level in {"DEBUG"}:
            log.debug(event.message)
        else:
            log.info(event.message)
