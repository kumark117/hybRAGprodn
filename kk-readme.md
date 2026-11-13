# HybridRAG — Requirements, Constraints & 15 Key Design Ideas

Repository: [kumark117/hybRAGprodn](https://github.com/kumark117/hybRAGprodn)  
Purpose: a production-oriented learning app demonstrating a hybrid Retrieval-Augmented Generation (RAG) backend and a live Next.js diagnostics UI.

## 1. Requirements

- **Backend:** Python 3.12+, FastAPI, asynchronous request handling; authenticated indexing and query APIs, including streaming endpoints.
- **Frontend:** Node 20+, Next.js + TypeScript; query console, answer/source display, and live pipeline Log Pane.
- **Retrieval:** combine dense semantic search (Pinecone) with lexical BM25; fuse, deduplicate and rerank candidates before building grounded context.
- **Generation:** LLM answers with source citations; support a fallback model/provider.
- **Indexing:** accept documents/chunks with metadata, embed and index them, preserving tenant ownership and source identity.
- **Operations:** Docker Compose for local Redis, FastAPI and frontend; tests, health endpoints, Prometheus metrics, structured logs and optional OpenTelemetry traces.
- **Evaluation:** Recall@K, Precision@K, MRR, HitRate and nDCG.
- **Local developer experience:** fake providers and in-memory stores allow tests/demo flows without paid API calls; Redis is optional locally.

## 2. Constraints and important caveats

- **Runtime versions:** Python 3.12+ and Node 20+.
- **External dependencies:** real generation needs LLM credentials; dense production retrieval needs Pinecone credentials/index; Redis is optional and can fail open when configured.
- **Demo defaults:** `USE_FAKE_PROVIDERS=true` uses mock LLM/hash embeddings/in-memory vector storage. These are for learning and tests, not production persistence or scale.
- **BM25 scaling limit:** the included BM25 store is process-local. It is suitable for one Uvicorn worker/tests, but replicas/workers will not share a consistent lexical corpus. Use OpenSearch/Elasticsearch (or another shared lexical index) for multi-replica production.
- **In-memory fake vector store:** likewise is not shared across workers or replicas; use Pinecone or another shared vector store in production.
- **SSE is best-effort diagnostics:** the bounded queue protects memory; low-priority events can be dropped for slow clients. The browser Log Pane is request-scoped and not a durable audit/log store.
- **Security must not degrade:** tenant authorization and tenant filters remain mandatory even when cache, vector search, BM25 or reranking degrades.
- **Production hardening remains necessary:** replace demo users with an IdP, use a secret manager, configure restrictive CORS, and send logs/traces/metrics to durable operational systems.
- **Numeric SLO/capacity targets:** repository documentation does not define a definitive throughput, latency, availability or concurrency SLO. These must be set and load-tested for the intended deployment.

## 3. Top 15 design ideas / methods

1. **Readable orchestration / separation of concerns** — `RAGService` coordinates the query path; indexing, retrieval, LLM, cache, security and observability are separate modules. Start with `backend/app/services/rag_service.py` and `backend/app/services/indexing_service.py`.
2. **Hybrid retrieval** — run dense semantic search and BM25 lexical search in parallel (`asyncio.gather`). Dense search finds paraphrases; BM25 catches exact terms, identifiers and rare keywords. See `docs/rag-pipeline.md`, `backend/app/services/rag_service.py`, `backend/app/retrieval/bm25_store.py`.
3. **Reciprocal Rank Fusion (RRF)** — combine ranked lists by rank, not raw scores, because BM25 and vector similarity scores are on different scales. Default `k=60`. See `backend/app/retrieval/fusion.py`.
4. **Candidate deduplication and provenance** — merge duplicate chunks while retaining vector rank, BM25 rank, RRF score and source identity, making retrieval explainable. See `backend/app/retrieval/dedup.py`, `backend/app/retrieval/fusion.py`.
5. **Two-stage retrieval then reranking** — inexpensive bi-encoder/ANN retrieval gathers a broader candidate set; a more expensive cross-encoder jointly scores query-document pairs and selects final top results. See `backend/app/retrieval/reranker.py`.
6. **Graceful degradation by component** — Pinecone failure can fall back to BM25-only; BM25 failure to vector-only; reranker failure keeps RRF order; Redis failure can bypass cache. Record degraded mode rather than treating every partial failure as total failure. See `docs/production-patterns.md`, `backend/app/services/rag_service.py`.
7. **Bounded retries with timeouts and jitter** — apply per-attempt timeouts; retry transient failures (e.g. 429/5xx/timeouts), not permanent validation/auth errors; exponential backoff plus jitter avoids synchronized retry storms. See `backend/app/core/retry.py`.
8. **Circuit breakers and provider failover** — CLOSED/OPEN/HALF_OPEN breakers stop repeatedly calling an unhealthy dependency; after retry budget exhaustion, switch to a fallback LLM/model. Retry, circuit breaking and failover solve different problems. See `backend/app/core/circuit_breaker.py`, `backend/app/llm/fallback_provider.py`, `docs/production-patterns.md`.
9. **Tenant isolation at multiple layers** — JWT establishes the principal; JWT tenant must match request tenant; Pinecone metadata filters and tenant-scoped BM25 prevent cross-tenant retrieval. Cache keys are tenant-aware. Authorization never fails open. See `docs/architecture.md`, `backend/app/core/security.py`, `backend/app/retrieval`.
10. **Cache correctness, not just speed** — exact cache keys include tenant, normalized query, filters, model/prompt and index/retrieval versions; embedding cache keys include text/model/version. Cache failures can fail open without crossing tenant boundaries. See `docs/rag-pipeline.md`, `backend/app/cache/`.
11. **Context budget and source diversity** — cap total context tokens and chunks per source; preserve chunk/document/source IDs for citations so one long document cannot crowd out the rest. See `backend/app/retrieval/context_builder.py`.
12. **Prompt-injection defense in depth** — retrieved documents are explicitly marked as untrusted data and instructed not to override system rules; retrieval-time tenant isolation remains the stronger security boundary. See `docs/rag-pipeline.md`, `backend/app/llm/prompts.py`.
13. **POST-based SSE streaming** — the browser uses `fetch()` + `ReadableStream` because native `EventSource` only supports GET, while query streaming is POST. Typed frames carry log events, tokens, citations and completion; heartbeats help keep connections alive. See `frontend/lib/sse.ts`, `backend/app/api/v1/query.py`, `docs/observability.md`.
14. **Bounded SSE backpressure and request-scoped events** — cap the event queue (`SSE_QUEUE_MAX_SIZE`); allow low-priority debug events to drop rather than grow memory without limit; keep each stream tied to its authenticated request/tenant. The Log Pane is diagnostic, not durable logging. See `backend/app/observability/event_bus.py`, `frontend/components/LogPane.tsx`, `docs/observability.md`.
15. **Three-pillar observability plus evaluation** — structured JSON logs explain events, Prometheus metrics show service trends, and OpenTelemetry traces expose stage latency. Propagate `request_id`; avoid high-cardinality metric labels such as user/request IDs. Evaluate retrieval with standard IR metrics and test simulated dependency failures. See `docs/observability.md`, `backend/app/observability/`, `backend/app/evaluation/`, `backend/tests/integration/test_failures.py`.

## 4. End-to-end flow in one glance

**Query:** Browser → Next.js → FastAPI middleware/auth/rate limit → tenant-aware cache → optional rewrite → parallel vector + BM25 retrieval → RRF → dedup → rerank → token-budgeted context → LLM (retry/fallback as needed) → answer + citations → response/SSE events.

**Indexing:** document + metadata → validation/chunking/embedding → dense and lexical indexes → tenant metadata retained for later filtered retrieval.

**Streaming UI:** FastAPI emits request-scoped events/tokens/citations → bounded SSE queue → frontend parser → Answer/Sources/Live Log Pane.

## 5. Best files to study first

- `docs/architecture.md` — components, runtime and security boundaries
- `docs/rag-pipeline.md` — retrieval, fusion, reranking, context and caching
- `docs/production-patterns.md` — retry, timeout, breaker, degradation and scaling
- `docs/observability.md` — logs vs metrics vs traces; SSE design
- `backend/app/services/rag_service.py` — main query orchestration
- `backend/app/services/indexing_service.py` — indexing orchestration
- `backend/app/retrieval/fusion.py` and `reranker.py` — retrieval quality stages
- `backend/app/core/retry.py` and `circuit_breaker.py` — resilience
- `backend/app/observability/event_bus.py` — event fan-out and SSE support
- `frontend/lib/sse.ts` and `frontend/components/LogPane.tsx` — browser streaming and UI

---

*Prepared from the repository README and its architecture, RAG pipeline, production-patterns, observability docs, and referenced implementation files. This is an architectural study note, not a claim that every demo default is production-ready.*
