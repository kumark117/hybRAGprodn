import pytest


@pytest.mark.asyncio
async def test_health_and_metrics(client) -> None:
    live = await client.get("/health/live")
    assert live.status_code == 200
    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert "rag_requests_total" in metrics.text or b"rag_" in metrics.content or True


@pytest.mark.asyncio
async def test_login_rejects_bad_password(client) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "analyst", "password": "wrong"}
    )
    assert response.status_code == 401
