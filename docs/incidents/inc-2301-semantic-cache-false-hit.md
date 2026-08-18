# Semantic cache served the wrong answer (INC-2301)

## Report

User asked “How do we rotate JWT_SECRET?” and received a polished answer about rotating **Pinecone** API keys. Exact strings differed. Cosine similarity of the two questions was 0.93. Threshold was 0.92. Semantic cache hit. Exact cache would have missed.

## Why this is dangerous

Semantic cache trades latency for correctness. Near-duplicate questions about **different secrets** are a classic false-positive.

## Policy

Keep `SEMANTIC_CACHE_ENABLED=false` until you have:

- per-tenant indexes of cached embeddings
- a high threshold (start at 0.97+, measure)
- an allowlist of question types (FAQ-only), not open-ended ops questions
- audit logs of cache hits with similarity scores (not full prompts in default logs)

Exact cache is boring and safe. Prefer it.

## Debug

Authorized debug mode may show `cache_type=semantic` and similarity. Do not log the raw question in production INFO logs.
