# BM25 replica inconsistency (INC-2044)

## The bug report

“I indexed retry-guide.md on the indexer pod. Query pods return ‘not enough evidence’.”

Error code users quoted: **E-2044** (stale lexical index). Support tickets also mentioned SKU `RETRY-POLICY-v3`.

## Root cause

The demo BM25 store is **process-local RAM**. Uvicorn worker A ingested the file. Worker B, C, and the next `docker compose` replica never saw it.

Dense Pinecone (when configured) is shared. Lexical search was not.

## What production should do

Put lexical retrieval behind OpenSearch, Elasticsearch, or a similar cluster. Keep the same `LexicalStore` interface (`search`, `upsert`, `delete_document`) so the orchestrator does not change.

Until then:

- run **one** API worker for demos (`uvicorn --workers 1`)
- or index **through the same process** that serves queries
- never assume `docker compose` replicas share BM25

## Why BM25 still matters

Error codes (`E-2044`), SKUs (`RETRY-POLICY-v3`), HTTP statuses (`429`), and acronyms (`TTFT`, `RRF`) often lose to embeddings. Hybrid search exists so those tokens still match.
