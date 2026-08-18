"""Run retrieval evaluation against the in-process BM25 + vector pipeline.

Usage (from backend/):
    python -m app.evaluation.run
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.container import build_container
from app.core.config import Settings
from app.core.logging import configure_logging
from app.evaluation.metrics import hit_rate, mean, mrr, ndcg_at_k, precision_at_k, recall_at_k
from app.observability.event_bus import NullEventSink
from app.schemas.index import IndexRequest
from app.schemas.query import QueryRequest

DOCS = {
    "retry-guide": (
        "Retries apply only to transient failures such as HTTP 429, 502, 503, 504, "
        "timeouts, and connection errors. Permanent errors including 400, 401, and 403 "
        "are never retried. Each attempt has an explicit timeout. Backoff is exponential "
        "with random jitter. After the retry budget is exhausted the system may fail over."
    ),
    "hybrid-search": (
        "Hybrid search runs dense Pinecone retrieval and BM25 lexical retrieval in parallel. "
        "Reciprocal Rank Fusion (RRF) combines ranks with score 1/(k+rank), typically k=60. "
        "Dense vectors capture semantic similarity. BM25 matches acronyms, IDs, and rare terms."
    ),
    "security": (
        "Every chunk stores tenant_id. Pinecone filters tenant_id before returning matches. "
        "BM25 only scores the tenant corpus. JWT tenant must match the requested tenant. "
        "Authorization is never degraded during failover."
    ),
    "observability": (
        "Time to first token (TTFT) is the delay from the start of the LLM request until the "
        "first streamed token. Correlation IDs, traces, metrics, and SSE live logs observe "
        "each RAG stage. Prometheus labels must not include request_id or user_id."
    ),
}


async def main() -> None:
    settings = Settings(USE_FAKE_PROVIDERS=True, REWRITE_ENABLED=False)
    configure_logging(settings)
    container = await build_container(settings)
    sink = NullEventSink()
    principal = container.auth.login("analyst", "analystpass")[1]

    for doc_id, text in DOCS.items():
        await container.indexing.index_document(
            IndexRequest(
                document_id=doc_id,
                tenant_id="tenant-a",
                text=text,
                metadata={"source": f"{doc_id}.md"},
            ),
            request_id=f"eval-{doc_id}",
            tenant_id="tenant-a",
            sink=sink,
        )

    dataset_path = Path(__file__).with_name("dataset.json")
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    recalls, precisions, mrrs, hits, ndcgs = [], [], [], [], []
    k = 5
    for row in cases:
        response = await container.rag.query(
            QueryRequest(query=row["question"], tenant_id="tenant-a", top_k=k, use_cache=False),
            principal,
            sink,
            request_id="eval-q",
        )
        retrieved = [s.document_id for s in response.sources]
        relevant = row["relevant_document_ids"]
        recalls.append(recall_at_k(retrieved, relevant, k))
        precisions.append(precision_at_k(retrieved, relevant, k))
        mrrs.append(mrr(retrieved, relevant))
        hits.append(hit_rate(retrieved, relevant, k))
        ndcgs.append(ndcg_at_k(retrieved, relevant, k))
        print(f"{row['question'][:48]:48} retrieved={retrieved} relevant={relevant}")

    print("\n=== Retrieval evaluation ===")
    print(f"Recall@{k}:    {mean(recalls):.3f}")
    print(f"Precision@{k}: {mean(precisions):.3f}")
    print(f"MRR:          {mean(mrrs):.3f}")
    print(f"HitRate@{k}:   {mean(hits):.3f}")
    print(f"nDCG@{k}:      {mean(ndcgs):.3f}")


if __name__ == "__main__":
    asyncio.run(main())
