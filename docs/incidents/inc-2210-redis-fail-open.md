# Redis down, cache fail-open (INC-2210)

## Symptom

Deploying Redis 7 with a wrong password: every query logged `cache_unavailable`. Product still answered. On-call almost rolled back a working RAG path.

## Policy

`CACHE_FAIL_OPEN=true` (default here): Redis errors skip cache and continue.

`CACHE_FAIL_OPEN=false`: cache is a hard dependency. Use only if a cache miss is worse than an outage (rare for RAG).

## What cache is for

- Exact query cache: same tenant + normalized question + models + prompt version
- Embedding cache: do not re-embed identical chunk text
- Optional semantic cache: similar questions (dangerous if threshold is sloppy)

Cache is **not** a source of truth. Pinecone + BM25 + LLM are.

## Never

- Cache across tenants (key must include `tenant_id`)
- Cache unauthenticated responses
- Treat the Next.js Log Pane as durable cache/debug storage

When Redis returns, expect a burst of cache fills. That is normal, not a stampede by itself (see cache-stampede.md).
