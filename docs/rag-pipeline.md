# RAG pipeline

```
QUERY
  |
Query normalization
  |
Optional rewrite
  |
  +----------+----------+
  |                     |
Pinecone              BM25
dense search        lexical search
  |                     |
  +----------+----------+
             |
            RRF
             |
        Deduplicate
             |
          Rerank
             |
     Context Builder
             |
            LLM
             |
    Answer + Citations
```

## Why hybrid search?

**Dense vectors** (bi-encoder + ANN) match paraphrases and semantic neighbors.
They miss rare tokens, error codes, SKUs, and exact identifiers when those
strings were never well represented in the embedding space.

**BM25** matches the terms that actually appear. It is strong on lexical
precision and weak on paraphrase.

Running both with `asyncio.gather` and fusing ranks covers both failure modes.

## Reciprocal Rank Fusion

Implemented in `backend/app/retrieval/fusion.py`:

```
RRF(d) = Σ  1 / (k + rank_i(d))
```

Default `k = 60`. We do **not** add raw BM25 scores to cosine similarities.
Those scores are not on a shared scale; ranks are.

Each fused candidate keeps `vector_rank`, `bm25_rank`, and `rrf_score`.

## Retrieval vs reranking

- Retrieval (bi-encoder): encode query and documents **separately**, compare vectors. Cheap, recall-oriented, top 20+20.
- Reranking (cross-encoder): score `(query, document)` **jointly**. Expensive, precision-oriented, top 5–8.

If the reranker fails, the pipeline keeps RRF order (graceful degradation).

## Context construction

`ContextBuilder` enforces:

- a token budget (`MAX_CONTEXT_TOKENS`)
- a per-source cap (`MAX_CHUNKS_PER_SOURCE`) so one PDF cannot dominate
- citation identity (chunk_id, document_id, source)

## Prompt injection mitigation

Retrieved text is wrapped in `<untrusted-document>` tags. The system prompt
states that those tags are data, not instructions, and cannot override system
rules. This is defense-in-depth, not a guarantee: keep tenant isolation at
retrieval time.

## Caching

Exact cache key includes tenant, normalized query, filters, LLM model,
embedding model, prompt version, index version, and retrieval config.
Embedding cache keys hash `(text, model, version)`.
Optional semantic cache compares query embeddings per tenant.

Cache **never** crosses tenants. Redis failure fail-opens when `CACHE_FAIL_OPEN=true`.

## Failure modes (educational)

| Failure | Behavior |
| --- | --- |
| Pinecone down after retries | `retrieval_mode=bm25_only`, `degraded_mode=true` |
| BM25 down | `vector_only` |
| Reranker down | RRF order |
| Redis down | skip cache if fail-open |
| Primary LLM exhausted | failover model |
| JWT tenant mismatch | 403, never retrieve |

Watch these transitions in the Live Log Pane: VECTOR timeout → RETRY → CIRCUIT → BM25-only → LLM → DONE.
