from app.models.document import Chunk, RetrievedChunk
from app.retrieval.dedup import deduplicate


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
        )
    )


def test_dedup_by_id_and_normalized_text() -> None:
    items = [
        _item("1", "Hello world"),
        _item("1", "Hello world"),
        _item("2", "Hello   world"),
        _item("3", "Different"),
    ]
    unique = deduplicate(items)
    assert [i.chunk_id for i in unique] == ["1", "3"]
