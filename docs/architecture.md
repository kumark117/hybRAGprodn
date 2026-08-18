# Architecture

This repository is a **learning-grade, production-oriented** hybrid RAG system:
a FastAPI retrieval/generation API and a Next.js console with a live log pane.

## Runtime view

```
                    Browser (Next.js)
                           |
                      Load balancer
                           |
               +-----------+-----------+
               |           |           |
           FastAPI 1   FastAPI 2   FastAPI N
               |           |           |
               +-----------+-----------+
                           |
           +---------------+----------------+
           |               |                |
         Redis          Pinecone         LLM APIs
           |
        Metrics  --> Prometheus
        Traces   --> OTEL collector
        Logs     --> Loki / ELK / CloudWatch / Datadog
```

API replicas are **stateless**. Redis holds cache and rate-limit counters.
Pinecone holds dense vectors. The LLM is an external HTTP API.

## Important demo vs production gap: BM25

The included `BM25Store` is **process-local**. It is correct for a single
Uvicorn worker and for tests. It will **not** stay consistent across multiple
FastAPI replicas. Production lexical search belongs in OpenSearch/Elasticsearch
(or a similar shared index) behind the same `LexicalStore` protocol.

## Backend layout

| Area | Responsibility |
| --- | --- |
| `services/rag_service.py` | Visible query orchestration |
| `services/indexing_service.py` | Visible index orchestration |
| `retrieval/` | Vector, BM25, RRF, dedup, rerank, context |
| `llm/` | Providers, failover, prompts, rewrite |
| `cache/` | Exact, embedding, optional semantic cache |
| `observability/` | Event bus, SSE, metrics, traces |
| `core/` | Retry, circuit breaker, JWT, rate limit |

## Request path

1. CORS + `RequestContextMiddleware` assigns `request_id` (`X-Request-ID`).
2. JWT auth binds `user_id` / `tenant_id`. Rate limiter runs per user and tenant.
3. Tenant in the JWT **must** match `tenant_id` in the body.
4. `RAGService.query` runs the pipeline and emits events to a composite sink:
   structured logs, Prometheus, and (for `/query/stream`) the request SSE queue.
5. The Next.js client parses SSE frames and updates Answer / Sources / Log Pane.

## Security boundaries that never degrade

- Tenant filter on vector search (`tenant_id` metadata filter).
- Tenant corpus on BM25.
- JWT tenant match.
- Prompt treats retrieved documents as untrusted data.

Failover, cache miss, and BM25-only mode **do not** skip authorization.
