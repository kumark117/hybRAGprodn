# TTFT SLO — time to first token

TTFT = time from **LLM request start** until the **first streamed token**.

Users feel TTFT as “the model started talking.” End-to-end latency includes retrieval + TTFT + remaining tokens.

## Incident INC-3112

Exact cache disabled in a misconfig. Every query waited on retrieval (~200ms) plus a cold LLM (~1.4s TTFT). Product thought “generation was broken” because the UI showed a blank answer panel until the first token. The Log Pane already showed VECTOR and BM25 complete.

## SLO sketch (example, not a promise)

- TTFT p50 < 400ms on cached-warm models
- TTFT p99 < 2s
- End-to-end p99 < 5s for hybrid RAG with rerank

Histogram: `rag_time_to_first_token_seconds`.

## Debugging a slow TTFT

1. Cache hit? Then LLM and retrieval were skipped — TTFT should be near zero client-side
2. Failover to a slower fallback model?
3. Semaphore wait (`MAX_LLM_CONCURRENCY`) — request queued behind others
4. Provider 429 + retry delay **before** the successful attempt
