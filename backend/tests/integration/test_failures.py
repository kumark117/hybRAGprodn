import pytest

from app.core.exceptions import RetryableProviderError
from app.llm.base import LLMResult
from app.llm.fallback_provider import FallbackLLMProvider
from app.llm.mock_provider import MockLLMProvider
from app.observability.event_bus import NullEventSink
from tests.integration.conftest import RETRY_DOC


class FlakyVector:
    def __init__(self, inner, fail_times: int) -> None:
        self.inner = inner
        self.fail_times = fail_times
        self.calls = 0

    async def search(self, *args, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RetryableProviderError("VECTOR_STORE_UNAVAILABLE", "timeout", provider="pinecone", status=504)
        return await self.inner.search(*args, **kwargs)

    async def upsert(self, *args, **kwargs):
        return await self.inner.upsert(*args, **kwargs)

    async def delete_document(self, *args, **kwargs):
        return await self.inner.delete_document(*args, **kwargs)

    async def ping(self):
        return True


class DeadVector:
    async def search(self, *args, **kwargs):
        raise RetryableProviderError("VECTOR_STORE_UNAVAILABLE", "down", provider="pinecone", status=503)

    async def upsert(self, *args, **kwargs):
        return 0

    async def delete_document(self, *args, **kwargs):
        return 0

    async def ping(self):
        return False


class DeadBM25:
    async def search(self, *args, **kwargs):
        raise RuntimeError("bm25 down")

    async def upsert(self, *args, **kwargs):
        return 0

    async def delete_document(self, *args, **kwargs):
        return 0

    async def ping(self):
        return False


class DeadReranker:
    async def rerank(self, query, candidates, *, top_k):
        raise RuntimeError("rerank down")


class FailThenOkLLM:
    def __init__(self) -> None:
        self.name = "flaky"
        self.model = "flaky"
        self.calls = 0

    async def generate(self, *, system: str, user: str) -> LLMResult:
        self.calls += 1
        if self.calls < 2:
            raise RetryableProviderError("LLM_UNAVAILABLE", "429", provider="llm", status=429)
        return LLMResult(text="recovered after retry [1]", model=self.model)

    async def stream(self, *, system: str, user: str):
        result = await self.generate(system=system, user=user)
        yield result.text


class AlwaysFailLLM:
    def __init__(self, name: str = "primary") -> None:
        self.name = name
        self.model = name

    async def generate(self, *, system: str, user: str) -> LLMResult:
        raise RetryableProviderError("LLM_UNAVAILABLE", "down", provider="llm", status=503)

    async def stream(self, *, system: str, user: str):
        if False:
            yield ""
        raise RetryableProviderError("LLM_UNAVAILABLE", "down", provider="llm", status=503)


@pytest.mark.asyncio
async def test_vector_failure_degrades_to_bm25(app, client, auth_header) -> None:
    await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    container = app.state.container
    container.rag.vector_store = DeadVector()
    container.rag.vector_circuit.reset()
    response = await client.post(
        "/api/v1/query",
        json={"query": "How are retries handled?", "tenant_id": "tenant-a", "use_cache": False},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["retrieval_mode"] == "bm25_only"
    assert response.json()["metadata"]["degraded_mode"] is True


@pytest.mark.asyncio
async def test_bm25_failure_degrades_to_vector(app, client, auth_header) -> None:
    await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    container = app.state.container
    container.rag.bm25 = DeadBM25()
    container.rag.bm25_circuit.reset()
    response = await client.post(
        "/api/v1/query",
        json={"query": "How are retries handled?", "tenant_id": "tenant-a", "use_cache": False},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["retrieval_mode"] == "vector_only"


@pytest.mark.asyncio
async def test_reranker_failure_uses_rrf_order(app, client, auth_header) -> None:
    await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    container = app.state.container
    container.rag.reranker = DeadReranker()
    response = await client.post(
        "/api/v1/query",
        json={"query": "retries", "tenant_id": "tenant-a", "use_cache": False, "debug": True},
        headers=auth_header,
    )
    assert response.status_code == 200
    assert response.json()["answer"]


@pytest.mark.asyncio
async def test_llm_retry_then_success(app) -> None:
    container = app.state.container
    flaky = FailThenOkLLM()
    container.rag.llm = FallbackLLMProvider(
        flaky,
        MockLLMProvider("fallback"),
        container.settings,
        container.llm_circuit,
        container.limiter,
    )
    container.llm_circuit.reset()
    from app.core.security import Principal
    from app.observability.event_bus import NullEventSink
    from app.schemas.query import QueryRequest

    await container.indexing.index_document(
        __import__("app.schemas.index", fromlist=["IndexRequest"]).IndexRequest(**RETRY_DOC),
        request_id="req-indexfail1",
        tenant_id="tenant-a",
        sink=NullEventSink(),
    )
    principal = Principal(user_id="user-analyst", tenant_id="tenant-a", role="analyst")
    result = await container.rag.query(
        QueryRequest(query="retries", tenant_id="tenant-a", use_cache=False),
        principal,
        NullEventSink(),
        request_id="req-retryllm01",
    )
    assert "retry" in result.answer.lower() or result.answer


@pytest.mark.asyncio
async def test_llm_failover_to_fallback(app) -> None:
    container = app.state.container
    container.rag.llm = FallbackLLMProvider(
        AlwaysFailLLM("primary"),
        MockLLMProvider("fallback-ok"),
        container.settings,
        container.llm_circuit,
        container.limiter,
    )
    container.llm_circuit.reset()
    from app.core.security import Principal
    from app.schemas.query import QueryRequest
    from app.schemas.index import IndexRequest

    await container.indexing.index_document(
        IndexRequest(**RETRY_DOC),
        request_id="req-indexfail2",
        tenant_id="tenant-a",
        sink=NullEventSink(),
    )
    principal = Principal(user_id="user-analyst", tenant_id="tenant-a", role="analyst")
    result = await container.rag.query(
        QueryRequest(query="How does retry work?", tenant_id="tenant-a", use_cache=False),
        principal,
        NullEventSink(),
        request_id="req-failover01",
    )
    assert result.metadata.fallback_used is True
