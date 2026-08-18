from app.models.document import Chunk, RetrievedChunk
from app.retrieval.context_builder import ContextBuilder


def _item(doc: str, tokens: int, index: int = 0) -> RetrievedChunk:
    text = ("alpha " * tokens).strip()
    return RetrievedChunk(
        chunk=Chunk(
            chunk_id=f"{doc}-{index}",
            tenant_id="t",
            document_id=doc,
            document_version="v1",
            chunk_index=index,
            source=doc,
            text=text,
            token_count=tokens,
        )
    )


def test_context_builder_respects_budget_and_source_cap() -> None:
    builder = ContextBuilder(max_tokens=50, max_chunks_per_source=2)
    ranked = [
        _item("a", 20, 0),
        _item("a", 20, 1),
        _item("a", 20, 2),
        _item("b", 20, 0),
        _item("c", 40, 0),
    ]
    built = builder.build(ranked)
    assert built.token_count <= 50
    assert sum(1 for c in built.chunks if c.chunk.source == "a") <= 2
    assert built.documents_represented >= 1


def test_preferred_source_can_exceed_default_cap() -> None:
    builder = ContextBuilder(max_tokens=200, max_chunks_per_source=2)
    ranked = [_item("notes.md", 20, i) for i in range(5)] + [_item("other.md", 20, 0)]
    built = builder.build(ranked, preferred_sources={"notes.md"})
    assert sum(1 for c in built.chunks if c.chunk.source == "notes.md") > 2
