from app.retrieval.bm25_store import BM25Store, tokenize
from app.models.document import Chunk
import pytest


def _chunk(cid: str, tenant: str, text: str, doc: str = "d1", source: str = "s.md") -> Chunk:
    return Chunk(
        chunk_id=cid,
        tenant_id=tenant,
        document_id=doc,
        document_version="v1",
        chunk_index=0,
        source=source,
        text=text,
    )


@pytest.mark.asyncio
async def test_bm25_ranks_lexical_match_and_isolates_tenants() -> None:
    store = BM25Store()
    await store.upsert(
        [
            _chunk("a1", "tenant-a", "Circuit breaker opens after consecutive failures"),
            _chunk("a2", "tenant-a", "Pinecone stores dense embedding vectors"),
            _chunk("b1", "tenant-b", "Circuit breaker secret document"),
        ]
    )
    results = await store.search("circuit breaker", tenant_id="tenant-a", top_k=5)
    assert results
    assert results[0].chunk_id == "a1"
    assert all(item.chunk.tenant_id == "tenant-a" for item in results)


def test_tokenize_lowercases() -> None:
    assert tokenize("HTTP 429 Too Many") == ["http", "429", "too", "many"]


@pytest.mark.asyncio
async def test_bm25_matches_source_filename() -> None:
    store = BM25Store()
    await store.upsert(
        [
            _chunk(
                "n1",
                "tenant-a",
                "What is RAG? Retrieve then generate.",
                doc="docs__interview-notes.md",
                source="docs/interview-notes.md",
            ),
            _chunk("o1", "tenant-a", "Pinecone stores dense embedding vectors", doc="pinecone-timeouts.md"),
        ]
    )
    results = await store.search("interview notes", tenant_id="tenant-a", top_k=2)
    assert results
    assert results[0].chunk_id == "n1"
