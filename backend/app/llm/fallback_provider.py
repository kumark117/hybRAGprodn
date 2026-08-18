"""Primary LLM with retry, then failover to a fallback provider.

Retry  = try the same provider again after a transient error.
Failover = switch to a different model/provider after the retry budget is gone.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Awaitable, Callable

from app.core.circuit_breaker import CircuitBreaker
from app.core.config import Settings
from app.core.retry import retry_async
from app.llm.base import LLMProvider, LLMResult
from app.observability.events import ObservabilityEvent
from app.observability.event_bus import EventSink
from app.observability.metrics import LLM_DURATION, PROMPT_TOKENS, COMPLETION_TOKENS, TTFT
from app.observability.timing import emit_simple


class FallbackLLMProvider:
    def __init__(
        self,
        primary: LLMProvider,
        fallback: LLMProvider,
        settings: Settings,
        circuit: CircuitBreaker,
        limiter,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.settings = settings
        self.circuit = circuit
        self.limiter = limiter
        self.name = "llm-failover"
        self.model = primary.model

    async def generate(
        self,
        *,
        system: str,
        user: str,
        sink: EventSink,
        request_id: str,
        tenant_id: str | None = None,
    ) -> LLMResult:
        async def _once() -> LLMResult:
            async with self.limiter.limit_llm():
                return await self.primary.generate(system=system, user=user)

        try:
            result = await self.circuit.call(
                lambda: retry_async(
                    _once,
                    max_attempts=self.settings.MAX_RETRIES,
                    timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
                    provider=self.primary.name,
                    operation_name="generate",
                    emit=sink.emit,
                    request_id=request_id,
                    tenant_id=tenant_id,
                    base_delay=self.settings.RETRY_BASE_SECONDS,
                    max_delay=self.settings.RETRY_MAX_SECONDS,
                ),
                emit=sink.emit,
                request_id=request_id,
                tenant_id=tenant_id,
            )
            PROMPT_TOKENS.inc(result.prompt_tokens)
            COMPLETION_TOKENS.inc(result.completion_tokens)
            return result
        except Exception:
            await emit_simple(
                sink,
                request_id=request_id,
                stage="LLM",
                event="primary_provider_failed",
                message="WARN LLM Primary model unavailable",
                level="WARN",
                tenant_id=tenant_id,
                metadata={"model": self.primary.model},
            )
            await emit_simple(
                sink,
                request_id=request_id,
                stage="FAILOVER",
                event="fallback_started",
                message="switching to fallback provider",
                level="WARN",
                tenant_id=tenant_id,
                metadata={"fallback_model": self.fallback.model},
            )
            try:
                async with self.limiter.limit_llm():
                    result = await retry_async(
                        lambda: self.fallback.generate(system=system, user=user),
                        max_attempts=self.settings.MAX_RETRIES,
                        timeout_seconds=self.settings.LLM_TIMEOUT_SECONDS,
                        provider=self.fallback.name,
                        operation_name="generate_fallback",
                        emit=sink.emit,
                        request_id=request_id,
                        tenant_id=tenant_id,
                    )
                result.fallback_used = True
                self.model = result.model
                await emit_simple(
                    sink,
                    request_id=request_id,
                    stage="LLM",
                    event="fallback_succeeded",
                    message="fallback provider succeeded",
                    level="OK",
                    tenant_id=tenant_id,
                    metadata={"model": result.model},
                )
                return result
            except Exception:
                await emit_simple(
                    sink,
                    request_id=request_id,
                    stage="FAILOVER",
                    event="fallback_failed",
                    message="fallback provider failed",
                    level="ERROR",
                    tenant_id=tenant_id,
                )
                raise

    async def stream(
        self,
        *,
        system: str,
        user: str,
        sink: EventSink,
        request_id: str,
        tenant_id: str | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> LLMResult:
        started = time.perf_counter()
        first_token_ms: float | None = None
        parts: list[str] = []
        fallback_used = False
        model = self.primary.model

        async def consume(provider: LLMProvider) -> None:
            nonlocal first_token_ms, model
            async with self.limiter.limit_llm():
                async for token in provider.stream(system=system, user=user):
                    if cancel and cancel():
                        break
                    if first_token_ms is None:
                        first_token_ms = (time.perf_counter() - started) * 1000
                        TTFT.observe(first_token_ms / 1000)
                        await emit_simple(
                            sink,
                            request_id=request_id,
                            stage="LLM",
                            event="first_token",
                            message=f"First token: {first_token_ms:.0f} ms",
                            level="OK",
                            duration_ms=first_token_ms,
                            tenant_id=tenant_id,
                        )
                    parts.append(token)
                    if on_token:
                        await on_token(token)

        try:
            await consume(self.primary)
        except Exception:
            await emit_simple(
                sink,
                request_id=request_id,
                stage="LLM",
                event="primary_provider_failed",
                message="Primary model unavailable",
                level="WARN",
                tenant_id=tenant_id,
            )
            await emit_simple(
                sink,
                request_id=request_id,
                stage="FAILOVER",
                event="fallback_started",
                message="switching to fallback provider",
                level="WARN",
                tenant_id=tenant_id,
            )
            parts.clear()
            first_token_ms = None
            started = time.perf_counter()
            await consume(self.fallback)
            fallback_used = True
            model = self.fallback.model
            await emit_simple(
                sink,
                request_id=request_id,
                stage="LLM",
                event="fallback_succeeded",
                message="fallback provider succeeded",
                level="OK",
                tenant_id=tenant_id,
            )

        total_ms = (time.perf_counter() - started) * 1000
        LLM_DURATION.observe(total_ms / 1000)
        text = "".join(parts)
        return LLMResult(
            text=text,
            model=model,
            completion_tokens=max(1, len(text.split())),
            fallback_used=fallback_used,
            time_to_first_token_ms=first_token_ms,
        )
