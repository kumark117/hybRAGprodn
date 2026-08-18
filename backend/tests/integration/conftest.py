from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["USE_FAKE_PROVIDERS"] = "true"
os.environ["REWRITE_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-only"
os.environ["RETRY_BASE_SECONDS"] = "0.01"
os.environ["RETRY_MAX_SECONDS"] = "0.05"
os.environ["CACHE_FAIL_OPEN"] = "true"

from app.core.config import get_settings
from app.main import create_app

get_settings.cache_clear()


@pytest.fixture
async def app_client():
    get_settings.cache_clear()
    application = create_app()
    try:
        transport = ASGITransport(app=application, lifespan="on")
    except TypeError:
        transport = ASGITransport(app=application)
        async with application.router.lifespan_context(application):
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield application, ac
            return
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield application, ac


@pytest.fixture
async def app(app_client):
    return app_client[0]


@pytest.fixture
async def client(app_client):
    return app_client[1]


@pytest.fixture
async def token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "analyst", "password": "analystpass"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


RETRY_DOC = {
    "document_id": "retry-guide",
    "tenant_id": "tenant-a",
    "text": (
        "The system retries transient failures such as timeouts, connection errors, "
        "and HTTP 429, 502, 503, 504. Permanent errors 400, 401, 403 are never retried. "
        "Backoff is exponential with jitter. After retries are exhausted the orchestrator "
        "fails over to a fallback model. Circuit breakers open after consecutive failures."
    ),
    "metadata": {"source": "retry-guide.md", "department": "engineering"},
}
