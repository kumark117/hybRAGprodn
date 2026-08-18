import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitState
from app.core.exceptions import CircuitOpenError


@pytest.mark.asyncio
async def test_circuit_opens_and_rejects() -> None:
    breaker = CircuitBreaker("test", failure_threshold=2, reset_seconds=30)

    async def boom() -> None:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        await breaker.call(boom)
    with pytest.raises(RuntimeError):
        await breaker.call(boom)
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        await breaker.call(boom)


@pytest.mark.asyncio
async def test_circuit_closes_after_half_open_success() -> None:
    breaker = CircuitBreaker("test", failure_threshold=1, reset_seconds=0)

    async def boom() -> None:
        raise RuntimeError("down")

    async def ok() -> str:
        return "yes"

    with pytest.raises(RuntimeError):
        await breaker.call(boom)
    result = await breaker.call(ok)
    assert result == "yes"
    assert breaker.state is CircuitState.CLOSED
