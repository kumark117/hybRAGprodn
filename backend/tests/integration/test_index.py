import pytest

from tests.integration.conftest import RETRY_DOC


@pytest.mark.asyncio
async def test_index_and_status(client, auth_header) -> None:
    response = await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["chunks_created"] >= 1
    assert body["vectors_indexed"] >= 1
    assert "X-Request-ID" in response.headers

    status = await client.get("/api/v1/index/retry-guide/status", headers=auth_header)
    assert status.status_code == 200
    assert status.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_index_is_idempotent(client, auth_header) -> None:
    first = await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    second = await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    assert first.json()["chunks_created"] == second.json()["chunks_created"]
