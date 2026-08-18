import pytest

from tests.integration.conftest import RETRY_DOC


@pytest.mark.asyncio
async def test_query_returns_answer_and_citations(client, auth_header) -> None:
    await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    response = await client.post(
        "/api/v1/query",
        json={
            "query": "How does the system handle retries?",
            "tenant_id": "tenant-a",
            "top_k": 4,
            "use_cache": False,
            "debug": True,
        },
        headers=auth_header,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answer"]
    assert body["metadata"]["retrieval_mode"] in {"hybrid", "vector_only", "bm25_only"}
    assert body["request_id"]
    assert isinstance(body["sources"], list)


@pytest.mark.asyncio
async def test_tenant_isolation_blocks_cross_tenant(client) -> None:
    login_a = await client.post(
        "/api/v1/auth/login", json={"username": "analyst", "password": "analystpass"}
    )
    header_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}
    await client.post("/api/v1/index", json=RETRY_DOC, headers=header_a)

    login_b = await client.post(
        "/api/v1/auth/login", json={"username": "other", "password": "otherpass"}
    )
    header_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}
    forbidden = await client.post(
        "/api/v1/query",
        json={"query": "retries", "tenant_id": "tenant-a"},
        headers=header_b,
    )
    assert forbidden.status_code == 403

    isolated = await client.post(
        "/api/v1/query",
        json={"query": "retries", "tenant_id": "tenant-b", "use_cache": False},
        headers=header_b,
    )
    assert isolated.status_code == 200
    assert isolated.json()["metadata"]["candidate_count"] == 0 or "enough evidence" in isolated.json()["answer"].lower()
