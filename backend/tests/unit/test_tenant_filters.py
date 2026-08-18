from app.models.document import Chunk
from app.retrieval.memory_store import InMemoryVectorStore
import pytest


@pytest.mark.asyncio
async def test_vector_store_filters_tenant() -> None:
    store = InMemoryVectorStore()
    a = Chunk(
        chunk_id="a",
        tenant_id="tenant-a",
        document_id="d",
        document_version="v1",
        chunk_index=0,
        source="s",
        text="retries with jitter",
    )
    b = Chunk(
        chunk_id="b",
        tenant_id="tenant-b",
        document_id="d",
        document_version="v1",
        chunk_index=0,
        source="s",
        text="retries with jitter",
    )
    await store.upsert([a, b], [[1.0, 0.0], [1.0, 0.0]])
    results = await store.search([1.0, 0.0], tenant_id="tenant-a", top_k=10)
    assert [r.chunk_id for r in results] == ["a"]
