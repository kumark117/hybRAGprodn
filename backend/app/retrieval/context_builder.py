"""Context builder: token budget, source diversity, citation retention.

Never concatenate unlimited chunks into the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.indexing.chunker import estimate_tokens
from app.models.document import RetrievedChunk


@dataclass
class BuiltContext:
    chunks: list[RetrievedChunk]
    token_count: int
    documents_represented: int
    candidates_in: int


class ContextBuilder:
    def __init__(self, max_tokens: int, max_chunks_per_source: int) -> None:
        self.max_tokens = max_tokens
        self.max_chunks_per_source = max_chunks_per_source

    def build(
        self,
        ranked: list[RetrievedChunk],
        *,
        preferred_sources: set[str] | None = None,
    ) -> BuiltContext:
        selected: list[RetrievedChunk] = []
        per_source: dict[str, int] = {}
        tokens = 0
        seen_docs: set[str] = set()
        preferred = preferred_sources or set()

        for item in ranked:
            source = item.chunk.source or item.chunk.document_id
            cap = 32 if source in preferred else self.max_chunks_per_source
            if per_source.get(source, 0) >= cap:
                continue
            chunk_tokens = item.chunk.token_count or estimate_tokens(item.chunk.text)
            if selected and tokens + chunk_tokens > self.max_tokens:
                continue
            if not selected and chunk_tokens > self.max_tokens:
                truncated = item.model_copy(deep=True)
                truncated.chunk.text = _truncate_tokens(item.chunk.text, self.max_tokens)
                truncated.chunk.token_count = self.max_tokens
                selected.append(truncated)
                tokens = self.max_tokens
                seen_docs.add(item.chunk.document_id)
                break
            selected.append(item)
            tokens += chunk_tokens
            per_source[source] = per_source.get(source, 0) + 1
            seen_docs.add(item.chunk.document_id)

        return BuiltContext(
            chunks=selected,
            token_count=tokens,
            documents_represented=len(seen_docs),
            candidates_in=len(ranked),
        )


def _truncate_tokens(text: str, max_tokens: int) -> str:
    return text[: max_tokens * 4]
