# Interview notes

Short answers you can say out loud. Details live in the code paths listed beside each topic.

## What is RAG?

Retrieval-Augmented Generation: retrieve relevant passages, put them in the prompt, then generate. The model is grounded in your corpus instead of relying only on parametric memory. See `rag_service.py`.

## Vector search vs BM25

Vector search compares embeddings (semantic similarity). BM25 scores term frequency with inverse document frequency (lexical match). Vectors catch paraphrases; BM25 catches exact IDs and rare tokens.

## Why hybrid search?

Because the two methods fail on different queries. Running both and fusing ranks raises recall without forcing a single scoring scale.

## RRF

Reciprocal Rank Fusion: `sum 1/(k + rank)` across lists. Typical `k=60`. Rank-only fusion avoids mixing incompatible raw scores. See `fusion.py`.

## Retrieval vs reranking

Retrieve broadly and cheaply (bi-encoder / BM25). Rerank a shortlist with a more expensive model that looks at query and document together.

## Bi-encoder vs cross-encoder

Bi-encoder encodes sides separately → vectors you can index. Cross-encoder jointly encodes the pair → better relevance, cannot pre-index easily. See `reranker.py`.

## Recall@K

Fraction of relevant documents that appear in the top K results. `|{retrieved ∩ relevant}| / |relevant|`.

## Precision@K

Fraction of the top K that are relevant. `hits_in_top_k / K`.

## MRR

Mean Reciprocal Rank: for each query, `1 / rank_of_first_relevant`, then average. Sensitive to the first hit.

## nDCG

Normalized Discounted Cumulative Gain: graded usefulness with logarithmic discount by rank, divided by the ideal ranking. See `evaluation/metrics.py`.

## Exact cache vs semantic cache

Exact: same tenant + normalized query + config → same answer. Semantic: similar embedding → maybe reuse. Semantic can serve the wrong answer if the threshold is sloppy; exact cannot.

## Timeout vs retry

Timeout caps one wait. Retry schedules another attempt after a transient error. See `docs/production-patterns.md`.

## Retry vs failover

Retry = same backend again. Failover = different backend after the budget is gone.

## Retry vs circuit breaker

Retry repeats a call. A circuit breaker stops calling a sick dependency so it (and you) can recover.

## Rate limiting vs concurrency limiting

Per-time-window caps vs in-flight caps. Both are needed.

## Liveness vs readiness

Live = don’t restart me yet. Ready = send me traffic.

## Authentication vs authorization

Who you are vs what you may access.

## Tenant isolation

Every chunk stores `tenant_id`. Filters apply **before** context is built. The LLM never sees another tenant’s text. JWT tenant must match.

## Prompt injection defense

Treat retrieved docs as untrusted data, wrap them in delimiters, instruct the model to ignore embedded instructions, and never let retrieval skip tenant checks.

## Structured logging

JSON events with stable fields (`request_id`, `stage`, `duration_ms`). No secrets, no full prompts in default logs.

## Metrics

Aggregated numeric time series (Prometheus). Counters, histograms, gauges. Low-cardinality labels only.

## Distributed tracing

A tree of spans for one request across components. OpenTelemetry is the portable API.

## Correlation IDs

`request_id` stitches logs together even when tracing is off.

## OpenTelemetry

Vendor-neutral traces/metrics/logs API and SDKs. This app exports OTLP when enabled.

## Prometheus

Pull-based metrics. Scrape `GET /metrics`. Do not put request IDs on labels.

## SSE

Server-Sent Events: HTTP server-to-client stream with `event:` / `data:` frames.

## SSE vs WebSocket

SSE is one-way over HTTP. WebSocket is bidirectional. RAG token+log streaming is one-way, so SSE.

## Why SSE for RAG

Tokens and pipeline logs only flow server → browser. POST + `fetch` ReadableStream covers auth better than EventSource GET.

## TTFT

Time until the first generated token. User-perceived start of the answer.

## Graceful degradation

Keep serving a worse-but-safe mode (BM25-only, no cache, no rerank) instead of 500s. Never degrade auth.

## Why design observability into the pipeline

If stages do not emit events, you cannot tell whether Pinecone, BM25, the reranker, or the LLM caused the latency. Adding prints later misses concurrent `asyncio.gather` overlaps, cache hits that skip the rest of the graph, and failover. The event bus in this repo is the teaching version of that discipline.
