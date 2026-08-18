# Cache stampede after TTL expiry

Also called dogpiling.

## What happens

A popular question (`What is our retry policy?`) is cached for `CACHE_TTL_SECONDS`. At expiry, 500 concurrent users miss together. All 500 embed, retrieve, rerank, and call the LLM. The LLM 429s. Retries amplify. p99 explodes.

## Mitigations (production)

- Slightly jitter TTLs per key so they do not expire on the same second
- Single-flight / request coalescing: one miss computes, others wait
- Serve stale-while-revalidate for exact cache (serve old answer, refresh in background)
- Concurrency limiter on LLM (`MAX_LLM_CONCURRENCY`) so the stampede queues instead of melting the vendor

This learning app uses TTL + fail-open. It does **not** implement single-flight. If you demo a stampede, you will see many parallel `EMBED` / `LLM` log lines.

## Detection

`rag_cache_misses_total` spike aligned with `rag_active_llm_requests` gauge and `rag_retries_total`.
