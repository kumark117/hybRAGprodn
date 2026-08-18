import asyncio

import pytest

from app.core.exceptions import PermanentProviderError, RetryableProviderError
from app.core.retry import compute_backoff_seconds, is_retryable_exception, retry_async


def test_retry_classification() -> None:
    assert is_retryable_exception(RetryableProviderError("T", "x", provider="p", status=429))
    assert is_retryable_exception(TimeoutError())
    assert not is_retryable_exception(PermanentProviderError("P", "x", provider="p", status=400))
    assert not is_retryable_exception(PermanentProviderError("P", "x", provider="p", status=401))


def test_backoff_is_bounded() -> None:
    for attempt in range(1, 8):
        delay = compute_backoff_seconds(attempt, base=0.4, max_wait=2.0)
        assert 0 <= delay <= 2.0


@pytest.mark.asyncio
async def test_retry_async_succeeds_after_transient_failure() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RetryableProviderError("T", "nope", provider="llm", status=429)
        return "ok"

    result = await retry_async(
        flaky,
        max_attempts=4,
        timeout_seconds=1,
        provider="llm",
        operation_name="gen",
        base_delay=0.01,
        max_delay=0.02,
    )
    assert result == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_async_does_not_retry_permanent() -> None:
    async def bad() -> None:
        raise PermanentProviderError("P", "no", provider="llm", status=400)

    with pytest.raises(PermanentProviderError):
        await retry_async(
            bad,
            max_attempts=3,
            timeout_seconds=1,
            provider="llm",
            operation_name="gen",
        )
