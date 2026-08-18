"""Reciprocal Rank Fusion.

RRF(d) = SUM over ranked lists  1 / (k + rank_i(d))

We do NOT add raw BM25 scores to cosine similarities. Those numbers live
on incompatible scales. RRF only uses rank, which is why it is the default
fusion method in hybrid search.

Typical k = 60. Smaller k emphasizes top ranks more strongly.
"""

from __future__ import annotations

from app.models.document import RetrievedChunk
from app.retrieval.bm25_store import tokenize


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[RetrievedChunk]],
    *,
    k: int = 60,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    merged: dict[str, RetrievedChunk] = {}

    for origin, ranked in ranked_lists.items():
        for rank, item in enumerate(ranked, start=1):
            chunk_id = item.chunk_id
            contribution = 1.0 / (k + rank)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + contribution
            existing = merged.get(chunk_id)
            if existing is None:
                clone = item.model_copy(deep=True)
                clone.rrf_score = contribution
                if origin == "vector":
                    clone.vector_rank = rank
                elif origin == "bm25":
                    clone.bm25_rank = rank
                merged[chunk_id] = clone
            else:
                existing.rrf_score = scores[chunk_id]
                if origin == "vector":
                    existing.vector_rank = rank
                    if existing.retrieval_score is None:
                        existing.retrieval_score = item.retrieval_score
                elif origin == "bm25":
                    existing.bm25_rank = rank

    fused = list(merged.values())
    fused.sort(key=lambda item: item.rrf_score or 0.0, reverse=True)
    for item in fused:
        item.rrf_score = scores[item.chunk_id]
        item.origin = "rrf"
    return fused


def boost_path_matches(query: str, ranked: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Promote chunks whose source/document_id shares query tokens.

    Dense retrieval misses filename queries ('interview notes' vs RAG crib content).
    Path overlap is a rank-only hint; it does not mix BM25 and cosine scores.
    """
    query_tokens = set(tokenize(query))
    if not query_tokens or not ranked:
        return ranked

    def sort_key(item: RetrievedChunk) -> tuple[float, float]:
        return (_path_overlap(query_tokens, item), item.rrf_score or item.retrieval_score or 0.0)

    return sorted(ranked, key=sort_key, reverse=True)


def preferred_sources(query: str, ranked: list[RetrievedChunk], *, min_overlap: float = 0.5) -> set[str]:
    """Sources whose path looks like the user named that document."""
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return set()
    names: set[str] = set()
    for item in ranked:
        if _path_overlap(query_tokens, item) >= min_overlap:
            names.add(item.chunk.source or item.chunk.document_id)
    return names


def _path_overlap(query_tokens: set[str], item: RetrievedChunk) -> float:
    path_tokens = set(tokenize(f"{item.chunk.source} {item.chunk.document_id}"))
    return len(query_tokens & path_tokens) / len(query_tokens)
