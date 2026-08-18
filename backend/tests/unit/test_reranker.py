import pytest

from app.models.document import Chunk, RetrievedChunk
from app.retrieval.reranker import LexicalOverlapReranker


def _item(cid: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=Chunk(
            chunk_id=cid,
            tenant_id="t",
            document_id="d",
            document_version="v1",
            chunk_index=0,
            source="s",
            text=text,
        ),
        rrf_score=0.01,
    )


@pytest.mark.asyncio
async def test_lexical_reranker_promotes_overlap() -> None:
    reranker = LexicalOverlapReranker()
    ranked = await reranker.rerank(
        "retry timeout jitter",
        [_item("a", "unrelated pineapple facts"), _item("b", "retry with timeout and jitter")],
        top_k=1,
    )
    assert ranked[0].chunk_id == "b"
    assert ranked[0].reranker_score is not None


@pytest.mark.asyncio
async def test_lexical_reranker_uses_source_path() -> None:
    reranker = LexicalOverlapReranker()
    other = _item("a", "What is RAG? Retrieve then generate.")
    notes = RetrievedChunk(
        chunk=Chunk(
            chunk_id="b",
            tenant_id="t",
            document_id="docs__interview-notes.md",
            document_version="v1",
            chunk_index=0,
            source="docs/interview-notes.md",
            text="What is RAG? Retrieve then generate.",
        ),
        rrf_score=0.01,
    )
    ranked = await reranker.rerank("interview notes", [other, notes], top_k=1)
    assert ranked[0].chunk_id == "b"
