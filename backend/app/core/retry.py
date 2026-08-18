"""Visible retry policy.

TIMEOUT = how long a single attempt may wait.
RETRY   = whether another attempt is scheduled after a transient failure.

This module is intentionally explicit so you can read the backoff math.
Tenacity supplies the jittered exponential wait; classification of retryable
errors is ours, because RAG providers fail in domain-specific ways.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from tenacity import RetryCallState
from tenacity.wait import wait_exponential_jitter

from app.core.exceptions import PermanentProviderError, RetryableProviderError
from app.observability.events import ObservabilityEvent, Stage

T = TypeVar("T")

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
PERMANENT_STATUS_CODES = {400, 401, 403, 404, 422}


def is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, PermanentProviderError):
        return False
    if isinstance(exc, RetryableProviderError):
        status = exc.upstream_status
        if status in PERMANENT_STATUS_CODES:
            return False
        return status is None or status in RETRYABLE_STATUS_CODES
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    name = type(exc).__name__.lower()
    return any(token in name for token in ("timeout", "connection", "unavailable", "rate"))


def classify_http_status(status: int, provider: str, message: str) -> Exception:
    if status in PERMANENT_STATUS_CODES:
        return PermanentProviderError(
            "PROVIDER_REJECTED",
            message,
            provider=provider,
            status=status,
        )
    if status in RETRYABLE_STATUS_CODES or status >= 500:
        return RetryableProviderError(
            "PROVIDER_TRANSIENT",
            message,
            provider=provider,
            status=status,
        )
    return PermanentProviderError("PROVIDER_ERROR", message, provider=provider, status=status)


def compute_backoff_seconds(
    attempt: int,
    *,
    base: float = 0.4,
    max_wait: float = 8.0,
) -> float:
    """Exponential backoff with full jitter.

    delay = random(0, min(max_wait, base * 2^(attempt-1)))
    """
    cap = min(max_wait, base * (2 ** (attempt - 1)))
    return random.uniform(0, cap)


_TENACITY_WAIT = wait_exponential_jitter(initial=0.4, max=8.0, jitter=0.5)


def tenacity_delay(attempt: int) -> float:
    """Use Tenacity's wait strategy so production backoff is not hand-rolled only."""
    state = RetryCallState(None, None, None, None)  # type: ignore[arg-type]
    state.attempt_number = attempt
    try:
        return float(_TENACITY_WAIT(state))
    except Exception:
        return compute_backoff_seconds(attempt)


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    timeout_seconds: float,
    provider: str,
    operation_name: str,
    emit: Callable[[ObservabilityEvent], Awaitable[None]] | None = None,
    request_id: str = "",
    tenant_id: str | None = None,
    base_delay: float = 0.4,
    max_delay: float = 8.0,
) -> T:
    """Run `operation` with per-attempt timeout, exponential backoff, and jitter.

    Permanent errors (400/401/403/validation) are never retried.
    """
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncio.wait_for(operation(), timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            last_error = RetryableProviderError(
                "PROVIDER_TIMEOUT",
                f"{provider} timed out during {operation_name}",
                provider=provider,
            )
            error_category = "timeout"
            retryable = attempt < max_attempts
            if emit:
                await emit(
                    ObservabilityEvent(
                        request_id=request_id,
                        level="WARN",
                        stage=_stage_for_provider(provider),
                        event="timeout",
                        message=f"Timeout attempt={attempt}",
                        tenant_id=tenant_id,
                        metadata={
                            "provider": provider,
                            "operation": operation_name,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "error_category": error_category,
                        },
                    )
                )
        except Exception as exc:  # noqa: BLE001 - classification happens next
            last_error = exc
            retryable = is_retryable_exception(exc) and attempt < max_attempts
            error_category = type(exc).__name__
            if emit:
                await emit(
                    ObservabilityEvent(
                        request_id=request_id,
                        level="WARN" if retryable else "ERROR",
                        stage=_stage_for_provider(provider),
                        event="operation_failed",
                        message=f"{provider} {operation_name} failed: {type(exc).__name__}",
                        tenant_id=tenant_id,
                        metadata={
                            "provider": provider,
                            "operation": operation_name,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "error_category": error_category,
                            "retryable": retryable,
                        },
                    )
                )
            if not retryable:
                raise

        if attempt >= max_attempts:
            break

        delay = compute_backoff_seconds(attempt, base=base_delay, max_wait=max_delay)
        if emit:
            await emit(
                ObservabilityEvent(
                    request_id=request_id,
                    level="INFO",
                    stage="RETRY",
                    event="retry_scheduled",
                    message=f"retrying in {delay:.2f} sec",
                    tenant_id=tenant_id,
                    metadata={
                        "provider": provider,
                        "operation": operation_name,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "delay_seconds": round(delay, 3),
                        "error_category": error_category,
                    },
                )
            )
        await asyncio.sleep(delay)

    if emit:
        await emit(
            ObservabilityEvent(
                request_id=request_id,
                level="ERROR",
                stage=_stage_for_provider(provider),
                event="retry_budget_exhausted",
                message="Retry budget exhausted",
                tenant_id=tenant_id,
                metadata={
                    "provider": provider,
                    "operation": operation_name,
                    "max_attempts": max_attempts,
                },
            )
        )
    assert last_error is not None
    raise last_error


def _stage_for_provider(provider: str) -> Stage:
    mapping: dict[str, Stage] = {
        "pinecone": "VECTOR",
        "vector": "VECTOR",
        "bm25": "BM25",
        "llm": "LLM",
        "openai": "LLM",
        "embedding": "EMBED",
        "reranker": "RERANK",
        "redis": "CACHE",
        "rewrite": "REWRITE",
    }
    return mapping.get(provider.lower(), "REQUEST")
