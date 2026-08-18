from app.models.document import Chunk, RetrievedChunk
from app.retrieval.fusion import reciprocal_rank_fusion


def _item(cid: str, origin: str) -> RetrievedChunk:
    chunk = Chunk(
        chunk_id=cid,
        tenant_id="t",
        document_id="d",
        document_version="v1",
        chunk_index=0,
        source="s",
        text=cid,
    )
    return RetrievedChunk(chunk=chunk, origin=origin, retrieval_score=1.0)


def test_rrf_prefers_items_high_in_both_lists() -> None:
    vector = [_item("both", "vector"), _item("only-v", "vector")]
    bm25 = [_item("both", "bm25"), _item("only-b", "bm25")]
    fused = reciprocal_rank_fusion({"vector": vector, "bm25": bm25}, k=60)
    assert fused[0].chunk_id == "both"
    assert fused[0].vector_rank == 1
    assert fused[0].bm25_rank == 1
    expected = 1 / 61 + 1 / 61
    assert abs((fused[0].rrf_score or 0) - expected) < 1e-9


def test_path_boost_promotes_filename_match() -> None:
    from app.retrieval.fusion import boost_path_matches

    rag = _item("rag", "rrf")
    notes = RetrievedChunk(
        chunk=Chunk(
            chunk_id="notes",
            tenant_id="t",
            document_id="docs__interview-notes.md",
            document_version="v1",
            chunk_index=0,
            source="docs/interview-notes.md",
            text="What is RAG? Retrieve then generate.",
        ),
        origin="rrf",
        rrf_score=0.01,
    )
    rag.rrf_score = 0.03
    boosted = boost_path_matches("interview notes", [rag, notes])
    assert boosted[0].chunk_id == "notes"


def test_preferred_sources_detects_named_file() -> None:
    from app.retrieval.fusion import preferred_sources

    rag = _item("rag", "rrf")
    notes = RetrievedChunk(
        chunk=Chunk(
            chunk_id="notes",
            tenant_id="t",
            document_id="docs__interview-notes.md",
            document_version="v1",
            chunk_index=0,
            source="docs/interview-notes.md",
            text="What is RAG?",
        ),
        origin="rrf",
        rrf_score=0.01,
    )
    assert preferred_sources("interview notes", [rag, notes]) == {"docs/interview-notes.md"}
