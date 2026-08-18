"""Prometheus metrics. Labels are low-cardinality on purpose.

Never put request_id, user_id, or raw query text on a metric label.
Those explode time-series cardinality and will melt Prometheus.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.observability.events import ObservabilityEvent

REQUESTS = Counter(
    "rag_requests_total",
    "RAG query requests",
    ["result", "retrieval_mode", "cache"],
)
REQUEST_DURATION = Histogram(
    "rag_request_duration_seconds",
    "End-to-end RAG query duration",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
INDEX_REQUESTS = Counter("rag_index_requests_total", "Index requests", ["result"])
INDEX_DURATION = Histogram("rag_index_duration_seconds", "Index duration")
CACHE_HITS = Counter("rag_cache_hits_total", "Cache hits", ["cache_type"])
CACHE_MISSES = Counter("rag_cache_misses_total", "Cache misses", ["cache_type"])
VECTOR_DURATION = Histogram("rag_vector_search_duration_seconds", "Pinecone search duration")
BM25_DURATION = Histogram("rag_bm25_search_duration_seconds", "BM25 search duration")
RRF_DURATION = Histogram("rag_rrf_duration_seconds", "RRF duration")
RERANK_DURATION = Histogram("rag_rerank_duration_seconds", "Rerank duration")
LLM_DURATION = Histogram("rag_llm_duration_seconds", "LLM generation duration")
TTFT = Histogram(
    "rag_time_to_first_token_seconds",
    "Time to first token from LLM request start",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
RETRIES = Counter("rag_retries_total", "Retry attempts", ["provider", "operation"])
FAILOVERS = Counter("rag_failovers_total", "Provider failovers", ["component"])
DEGRADED = Counter("rag_degraded_requests_total", "Degraded retrieval mode", ["mode"])
ERRORS = Counter("rag_errors_total", "Application errors", ["code", "stage"])
CHUNKS_INDEXED = Counter("rag_chunks_indexed_total", "Chunks written to indexes")
RETRIEVAL_CANDIDATES = Histogram(
    "rag_retrieval_candidates",
    "Candidate counts after fusion",
    buckets=(1, 5, 10, 20, 40, 80),
)
CONTEXT_TOKENS = Histogram("rag_context_tokens", "Tokens placed into context")
PROMPT_TOKENS = Counter("rag_prompt_tokens_total", "Prompt tokens sent to the LLM")
COMPLETION_TOKENS = Counter("rag_completion_tokens_total", "Completion tokens from the LLM")


class MetricsSink:
    async def emit(self, event: ObservabilityEvent) -> None:
        name = event.event
        if name == "retry_scheduled":
            RETRIES.labels(
                str(event.metadata.get("provider", "unknown")),
                str(event.metadata.get("operation", "unknown")),
            ).inc()
        elif name in {"fallback_started", "primary_provider_failed"}:
            FAILOVERS.labels(str(event.stage)).inc()
        elif name == "cache_hit":
            CACHE_HITS.labels(str(event.metadata.get("cache_type", "exact"))).inc()
        elif name == "cache_miss":
            CACHE_MISSES.labels(str(event.metadata.get("cache_type", "exact"))).inc()
        elif name in {"timeout", "operation_failed", "retry_budget_exhausted"}:
            ERRORS.labels(name, str(event.stage)).inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
