# Reranker outage — keep RRF order

Cross-encoder rerankers (local MiniLM, Cohere Rerank, Jina) are **precision** tools on a shortlist. They are not required for a correct-enough demo answer.

## Policy

If rerank fails or the circuit opens:

- do **not** fail the query
- use Reciprocal Rank Fusion order (or the single surviving retriever)
- log `rerank_fallback`

Users may see slightly noisier citations. That is better than a blank page.

## Why not skip retrieval instead?

Retrieval produces candidates. Rerank only reorders them. Skipping rerank still leaves context. Skipping retrieval leaves the LLM ungrounded.

## Bi-encoder vs cross-encoder

Bi-encoder: encode query and docs separately (Pinecone). Cheap, recall-oriented.

Cross-encoder: score `(query, document)` jointly. Expensive, precision-oriented, top 5–8 only.
