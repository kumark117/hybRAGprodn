"""Near-duplicate removal after fusion."""

from __future__ import annotations

from app.indexing.ids import normalize_chunk_content
from app.models.document import RetrievedChunk


def deduplicate(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen_ids: set[str] = set()
    seen_text: set[str] = set()
    unique: list[RetrievedChunk] = []
    for item in chunks:
        text_key = normalize_chunk_content(item.chunk.text)
        if item.chunk_id in seen_ids or text_key in seen_text:
            continue
        seen_ids.add(item.chunk_id)
        if text_key:
            seen_text.add(text_key)
        unique.append(item)
    return unique
