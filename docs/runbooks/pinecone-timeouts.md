# Pinecone timeouts and vector brownouts

Error codes: `VECTOR_STORE_UNAVAILABLE`, upstream 504, gRPC DEADLINE_EXCEEDED.

## Typical symptoms

- Live log: `START VECTOR` then silence past `PINECONE_TIMEOUT_SECONDS`
- Metrics: `rag_vector_search_duration_seconds` saturates the histogram
- Users still get answers if BM25 is healthy (`retrieval_mode=bm25_only`)

## Why dense search fails independently of BM25

Pinecone is a network hop. BM25 in this learning app is in-process. A VPC blip, TLS handshake stall, or control-plane issue can kill vectors while lexical search still works.

That is why hybrid retrieval uses `asyncio.gather` and **partial failure**:

- vector down + BM25 up → continue
- never 500 the whole query if one retriever dies

## Production notes

True multi-replica production still needs a **shared** vector index (Pinecone, Qdrant, Weaviate, pgvector with a primary). Process-local fake vectors are for tests only.

Filter `tenant_id` **in the query**, not after fetch. Fetching another tenant’s vectors and hoping the LLM ignores them is not isolation.

## Runbook

1. Check `/health/ready` — `vector` may be `degraded`
2. Confirm `PINECONE_API_KEY` and index name
3. Confirm dimension matches the embedding model (see embedding-dimension-mismatch.md)
4. Watch circuit state; do not bounce pods just to “clear” an OPEN circuit unless it is stuck
