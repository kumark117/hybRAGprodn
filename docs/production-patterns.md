# Production patterns

## Timeout vs retry

- **Timeout**: how long **one attempt** may wait (`LLM_TIMEOUT_SECONDS`, `PINECONE_TIMEOUT_SECONDS`, …). Infinite waits are forbidden.
- **Retry**: whether **another attempt** is scheduled after a *transient* failure.

A timeout can trigger a retry. A 400 validation error must not.

Retries use exponential backoff **plus jitter** so thundering herds do not retry in lockstep.

Do not retry 400, 401, 403, or schema failures.

## Retry vs failover

- **Retry**: same provider, another attempt.
- **Failover**: different provider/model after the retry budget is exhausted (`fallback_used=true`).

## Retry vs circuit breaker

- **Retry** asks: “try this call again?”
- **Circuit breaker** asks: “should we attempt this dependency *at all* right now?”

States: CLOSED (normal) → OPEN (fail fast) → HALF_OPEN (one trial). Retries against an OPEN circuit become a retry storm. The breaker sheds load so the dependency can recover.

## Rate limiting vs concurrency limiting

- **Rate limiting**: max operations **per time window** (per user / per tenant). Returns 429.
- **Concurrency limiting**: max **in-flight** expensive calls (`asyncio.Semaphore` for LLM, embeddings, rerank). Protects GPU/API quotas even if 429s are slow to arrive.

## Graceful degradation

Partial retrieval failure is not a hard 500:

- vector down, BM25 up → `bm25_only`
- BM25 down, vector up → `vector_only`
- reranker down → RRF order
- Redis down → continue if `CACHE_FAIL_OPEN`

**Never** degrade tenant authorization.

## Liveness vs readiness

- `/health/live`: process is running (do not kill the pod).
- `/health/ready`: safe to send traffic. Optional Redis being down can be “degraded” without failing liveness.

## Authentication vs authorization

- **Authentication**: who are you? (JWT)
- **Authorization**: are you allowed to touch this tenant’s chunks? (JWT `tenant_id` == request `tenant_id`, plus store-level filters)

## SSE backpressure

`SSE_QUEUE_MAX_SIZE` (default 500) bounds memory. If the browser is slow, debug/info events drop first. Document this: completeness of the Log Pane is best-effort; ERROR/DONE try to survive.

## Horizontal scaling

Uvicorn workers do not share the in-memory BM25 index or in-memory vector fake. For multi-replica production:

- Pinecone (or equivalent) for dense search
- OpenSearch/Elasticsearch for lexical search
- Redis for cache and rate limits
- no sticky in-process corpus

## CORS

Development allows configured localhost origins. Production must not default to `*`.
