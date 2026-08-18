import pytest

from app.cache.cache_service import CacheService
from app.core.config import Settings


@pytest.mark.asyncio
async def test_cache_fail_open_returns_none() -> None:
    class Boom:
        async def get(self, key: str) -> str | None:
            raise ConnectionError("redis down")

        async def set(self, key: str, value: str, ttl_seconds: int) -> None:
            raise ConnectionError("redis down")

    service = CacheService(Boom(), Settings(), fail_open=True)
    assert await service.get_json("k") is None
    await service.set_json("k", {"ok": True})
