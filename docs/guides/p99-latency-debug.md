# Debugging p99 RAG latency

Work top-down using **one request_id** from `X-Request-ID` or the Log Pane.

1. Cache hit? If yes, p99 should be tiny. If p99 is huge and cache hit rate is high, you are measuring something else (client, SSE buffer).
2. Step timings in debug metadata: `rewrite_ms`, `embedding_ms`, `pinecone_ms`, `bm25_ms`, `rerank_ms`, `llm_first_token_ms`, `llm_total_ms`
3. Overlapping VECTOR and BM25 start times prove `asyncio.gather` is actually concurrent
4. Retry delays are **inside** those step times — look for `retry_scheduled`
5. Semaphore delay does not always have its own timer; rising `rag_active_llm_requests` plus slow TTFT implies queueing

Do not average p99 across cache-hit and cache-miss traffic. Split the Prometheus histogram by the `cache` label (`hit` vs `miss`).
