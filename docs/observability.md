# Observability

Observability is designed into the pipeline, not bolted on after the first outage.

## Logs vs metrics vs traces

| Pillar | Question it answers | This app |
| --- | --- | --- |
| **Logs** | What happened on *this* request? | structlog JSON + SSE `event: log` |
| **Metrics** | How is the *service* behaving over time? | Prometheus `/metrics` |
| **Traces** | Where did time go across spans/services? | OpenTelemetry spans `rag.*` |

Use all three. Logs without metrics cannot show SLO burn. Metrics without traces cannot explain a slow percentile. Traces without logs lack the message you needed at 2am.

## Correlation ID (`request_id`)

A client-facing identifier for **one HTTP request**. Generated if the client did not send a valid `X-Request-ID`. Returned on `X-Request-ID`. Propagated through RAGService, cache, retrieval, LLM, SSE, and the Log Pane.

You can grep production logs for `request_id=req-…` and reconstruct the journey.

## `trace_id` and `span_id`

When OpenTelemetry is enabled:

- **trace_id**: one distributed trace (the whole query, possibly across services).
- **span_id**: one unit of work inside that trace (`rag.rerank`, `rag.retrieve.vector`, …).

A request can have one `request_id` and one `trace_id`. Spans nest under the trace.

## Why not put `user_id` / `request_id` on Prometheus labels?

**High-cardinality telemetry** means a label that takes on huge numbers of distinct values (every user, every request, every raw query). Prometheus stores a time series **per label combination**. Exploding cardinality:

- burns memory
- slows queries
- makes recording rules unusable
- can take down the monitoring system that you needed during the incident

Safe labels: `retrieval_mode`, `cache`, `provider`, `result`, `stage`.
Unsafe labels: `request_id`, `user_id`, `query_text`, `document_id` at high volume.

Keep those fields on **logs and traces**, not metric labels.

## TTFT (time to first token)

TTFT is the time from **the start of the LLM call** until the **first streamed token**. It is the number users feel as “the model started talking.”

We also record end-to-end latency until `done`. Prometheus histogram: `rag_time_to_first_token_seconds`.

## How SSE transports logs to the browser

`POST /api/v1/query/stream` returns `text/event-stream`. One connection carries typed frames:

```
event: log
data: {"stage":"RERANK","message":"..."}

event: token
data: {"text":"The"}

event: citation
data: {...}

event: done
data: {"latency_ms":1942,"retrieval_mode":"hybrid"}
```

Frames are written as stages complete — not buffered until the end. Heartbeats (`: heartbeat`) keep proxies from idling out the connection. The queue is **bounded**; a slow tab cannot grow memory without limit. Low-priority debug events may drop; ERROR/DONE are preserved when possible.

The stream is **request-scoped**. Tenant A cannot subscribe to Tenant B’s events.

## The Log Pane is not the production log store

The Next.js Live Log Pane is a **request-scoped diagnostic and learning UI**. It exists so you can *see* CACHE, VECTOR ∥ BM25, retries, and failover as they happen.

It is **not** durable. Closing the tab loses it. It is not searchable across incidents. It is not an audit trail.

Production logs belong in a log backend:

- ELK / OpenSearch
- Grafana Loki
- Datadog
- CloudWatch
- Azure Monitor
- GCP Cloud Logging

Those systems ingest the same structured JSON `StructuredLogSink` already emits. You do not need them running locally to develop this app.

## SSE vs WebSocket

**SSE**: HTTP response, server → client, automatic `event:`/`data:` framing, reconnect semantics, simple auth via the original POST. Ideal when the server is pushing tokens and logs.

**WebSocket**: bidirectional persistent socket. Use it when the client must continuously send as well as receive (collaborative editors, multiplayer).

This product is dominated by server-to-client streaming, so SSE is the fit.

## Local tracing

`OTEL_ENABLED=false` by default. The process still creates spans in-process; nothing breaks if no collector listens. Set `OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT` to export.
