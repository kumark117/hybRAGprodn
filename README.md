# Hybrid RAG — production learning app

FastAPI hybrid retrieval (Pinecone + BM25 + RRF + rerank) with retries, failover, circuit breakers, Redis caching, JWT tenant isolation, Prometheus, OpenTelemetry, and **SSE live pipeline logs** rendered in a Next.js Log Pane.

This is a learning project. Important machinery stays visible in Python and TypeScript — not hidden behind a mega-framework.

## Architecture

See [docs/architecture.md](docs/architecture.md). Pipeline: [docs/rag-pipeline.md](docs/rag-pipeline.md). Observability: [docs/observability.md](docs/observability.md). Production patterns: [docs/production-patterns.md](docs/production-patterns.md). Interview crib: [docs/interview-notes.md](docs/interview-notes.md).

```
Browser → Next.js → FastAPI replicas → Redis / Pinecone / LLM
                      │
                 logs, metrics, traces
```

## Local setup

Requires Python 3.12+ and Node 20+. Redis is optional locally (in-memory cache is used if Redis is down and `CACHE_FAIL_OPEN=true`).

### Backend venv

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

Default `USE_FAKE_PROVIDERS=true` so tests and the demo UI work **without paid API calls**. BM25 and the in-memory vector store run in-process.

### Environment variables

Copy `backend/.env.example`. Important knobs:

| Variable | Purpose |
| --- | --- |
| `USE_FAKE_PROVIDERS` | Mock LLM + hash embeddings + in-memory vectors |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_FALLBACK_MODEL` | Real generation |
| `PINECONE_API_KEY` / `PINECONE_INDEX` | Dense retrieval |
| `REDIS_URL` | Cache + rate limits |
| `JWT_SECRET` | Signing key — never commit a real secret |
| `OTEL_ENABLED` | Export traces |
| `SSE_QUEUE_MAX_SIZE` | Backpressure on live logs |

### Pinecone

Create an index with the embedding dimension of your model (e.g. 1536 for `text-embedding-3-small`). The app upserts metadata including `tenant_id` and **filters on it at query time**.

### Redis

```bash
docker run -p 6379:6379 redis:7-alpine
```

If Redis is absent, the API still serves queries using an in-memory cache.

### Frontend

```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 → Query console.

## Docker

```bash
docker compose up --build
```

Starts Redis, FastAPI (`:8000`), and Next.js (`:3000`). LLM and Pinecone remain external (or stay on fakes via `.env.example`).

## Login

Demo users (learning only):

| User | Password | Tenant |
| --- | --- | --- |
| analyst | analystpass | tenant-a |
| admin | adminpass | tenant-a |
| other | otherpass | tenant-b |

## Indexing

Non-streaming:

```bash
curl -s http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d "{\"username\":\"analyst\",\"password\":\"analystpass\"}"
```

```bash
curl -s http://localhost:8000/api/v1/index -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"document_id\":\"retry-guide\",\"tenant_id\":\"tenant-a\",\"text\":\"Retries use exponential backoff with jitter. Permanent 400/401/403 errors are not retried.\",\"metadata\":{\"source\":\"retry-guide.md\"}}"
```

Streaming index (watch the Log Pane or curl):

```bash
curl -N http://localhost:8000/api/v1/index/stream -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"document_id\":\"retry-guide\",\"tenant_id\":\"tenant-a\",\"text\":\"Retries use exponential backoff with jitter.\",\"metadata\":{\"source\":\"retry-guide.md\"}}"
```

### Index a whole folder

Keep the backend running, then from `backend/`:

```bash
python -m app.cli index-folder ..\docs
python -m app.cli index-folder C:\notes --username analyst --password analystpass --tenant tenant-a
```

Or: `make index-folder DIR=../docs`

The CLI posts each `.md`/`.txt`/source file to the live API so Uvicorn's in-memory BM25 and vector stores actually receive them. In the UI, open **Indexing** and use **Select folder**.

## Query

```bash
curl -s http://localhost:8000/api/v1/query -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"query\":\"How does the system handle retries?\",\"tenant_id\":\"tenant-a\",\"debug\":true}"
```

Streaming query (tokens + live logs):

```bash
curl -N http://localhost:8000/api/v1/query/stream -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d "{\"query\":\"How does the system handle retries?\",\"tenant_id\":\"tenant-a\"}"
```

In the UI, keep **Stream** checked. The **Live RAG Log** pane auto-scrolls through CACHE, REWRITE, EMBED, VECTOR ∥ BM25, RRF, DEDUP, RERANK, CONTEXT, LLM, retries, failover, and COMPLETE.

## Observability

- Structured JSON logs on stdout
- `GET /metrics` Prometheus
- `OTEL_ENABLED=true` for OTLP traces
- `X-Request-ID` on every response
- Live SSE events are **request-scoped diagnostics**, not the production log store

```bash
curl -s http://localhost:8000/health/live
curl -s http://localhost:8000/health/ready
curl -s http://localhost:8000/metrics
```

## Tests

```bash
make backend-test
make frontend-check
# or
cd backend && python -m pytest
cd frontend && npm test && npm run typecheck
```

Tests use mocks/fakes. They do not call paid APIs.

## Evaluation

```bash
cd backend && python -m app.evaluation.run
```

Prints Recall@K, Precision@K, MRR, HitRate, nDCG against a tiny built-in corpus.

## Failure simulations

Integration tests in `backend/tests/integration/test_failures.py` cover:

- Pinecone down → BM25-only
- BM25 down → vector-only
- Reranker down → RRF order
- LLM 429 → retry → success
- Primary LLM dead → fallback
- Tenant A token querying tenant B → 403

## Production considerations

- Replace demo JWT users with a real IdP.
- Replace in-process BM25 with OpenSearch/Elasticsearch when you run multiple replicas.
- Put secrets in a secret manager. Never commit `.env`.
- Scrape `/metrics` with Prometheus; ship JSON logs to Loki/ELK/Datadog; export OTLP to a collector.
- Do not put `request_id` or `user_id` on Prometheus labels (cardinality).
- CORS must not be `*` in production.

## First files to study

1. `backend/app/services/rag_service.py`
2. `backend/app/services/indexing_service.py`
3. `backend/app/observability/event_bus.py`
4. `backend/app/api/v1/query.py`
5. `backend/app/retrieval/bm25_store.py`
6. `backend/app/retrieval/fusion.py`
7. `backend/app/retrieval/reranker.py`
8. `backend/app/core/retry.py`
9. `frontend/lib/sse.ts`
10. `frontend/components/LogPane.tsx`
11. `docs/observability.md`
12. `docs/interview-notes.md`
