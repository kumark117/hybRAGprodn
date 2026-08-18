"""Circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED.

Retry asks "try this call again?"
A circuit breaker asks "should we even attempt this dependency right now?"

After enough consecutive failures the circuit opens and fail-fast rejects
calls for a cooldown. A single trial in HALF_OPEN decides whether to close
or reopen. This protects downstreams and avoids retry storms.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypeVar

from app.core.exceptions import CircuitOpenError
from app.observability.events import ObservabilityEvent, Stage

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        reset_seconds: float = 30.0,
        stage: Stage = "REQUEST",
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.stage = stage
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_inflight = False

    @property
    def state(self) -> CircuitState:
        self._maybe_transition_to_half_open()
        return self._state

    def _maybe_transition_to_half_open(self) -> None:
        if self._state is CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.reset_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_inflight = False

    async def call(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        emit: Callable[[ObservabilityEvent], Awaitable[None]] | None = None,
        request_id: str = "",
        tenant_id: str | None = None,
    ) -> T:
        self._maybe_transition_to_half_open()

        if self._state is CircuitState.OPEN:
            if emit:
                await emit(self._event("circuit_call_rejected", "WARN", "Circuit open; call rejected"))
            raise CircuitOpenError(self.name)

        if self._state is CircuitState.HALF_OPEN:
            if self._half_open_inflight:
                if emit:
                    await emit(
                        self._event(
                            "circuit_call_rejected",
                            "WARN",
                            "Half-open trial already in flight",
                            request_id=request_id,
                            tenant_id=tenant_id,
                        )
                    )
                raise CircuitOpenError(self.name)
            self._half_open_inflight = True
            if emit:
                await emit(
                    self._event(
                        "circuit_half_open",
                        "INFO",
                        "Circuit half-open; allowing trial call",
                        request_id=request_id,
                        tenant_id=tenant_id,
                    )
                )

        try:
            result = await operation()
        except Exception:
            await self._on_failure(emit, request_id, tenant_id)
            raise
        else:
            await self._on_success(emit, request_id, tenant_id)
            return result
        finally:
            self._half_open_inflight = False

    async def _on_success(
        self,
        emit: Callable[[ObservabilityEvent], Awaitable[None]] | None,
        request_id: str,
        tenant_id: str | None,
    ) -> None:
        was_openish = self._state in {CircuitState.OPEN, CircuitState.HALF_OPEN}
        self._failures = 0
        self._state = CircuitState.CLOSED
        if was_openish and emit:
            await emit(
                self._event(
                    "circuit_closed",
                    "INFO",
                    "Circuit closed after successful trial",
                    request_id=request_id,
                    tenant_id=tenant_id,
                )
            )

    async def _on_failure(
        self,
        emit: Callable[[ObservabilityEvent], Awaitable[None]] | None,
        request_id: str,
        tenant_id: str | None,
    ) -> None:
        self._failures += 1
        if self._state is CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            if emit:
                await emit(
                    self._event(
                        "circuit_opened",
                        "ERROR",
                        f"Circuit opened after {self._failures} failures",
                        request_id=request_id,
                        tenant_id=tenant_id,
                    )
                )

    def _event(
        self,
        event: str,
        level: str,
        message: str,
        request_id: str = "",
        tenant_id: str | None = None,
    ) -> ObservabilityEvent:
        return ObservabilityEvent(
            request_id=request_id,
            level=level,  # type: ignore[arg-type]
            stage=self.stage,
            event=event,
            message=message,
            tenant_id=tenant_id,
            metadata={
                "circuit": self.name,
                "state": self._state.value,
                "failures": self._failures,
            },
        )

    def force_open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._half_open_inflight = False
