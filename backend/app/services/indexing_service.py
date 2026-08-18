"""Indexing orchestrator.

validate → clean → chunk → deterministic IDs → embed batches → Pinecone → BM25
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ValidationAppError
from app.core.retry import retry_async
from app.indexing.chunker import build_chunks, chunk_text, extract_title, with_title_prefix
from app.indexing.cleaner import clean_document
from app.indexing.ids import make_chunk_id, make_document_key
from app.llm.base import EmbeddingProvider
from app.models.document import Chunk
from app.observability.event_bus import EventSink
from app.observability.metrics import CHUNKS_INDEXED, INDEX_DURATION, INDEX_REQUESTS
from app.observability.timing import TimingCollector, emit_simple
from app.observability.tracing import stage_span
from app.retrieval.bm25_store import LexicalStore
from app.retrieval.vector_store import VectorStore
from app.schemas.index import IndexRequest, IndexResult, IndexStatus

StatusStore = dict[str, IndexStatus]


class IndexingService:
    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingProvider,
        vector_store: VectorStore,
        bm25: LexicalStore,
        limiter,
        cache,
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.bm25 = bm25
        self.limiter = limiter
        self.cache = cache
        self.status: StatusStore = {}

    async def index_document(
        self,
        request: IndexRequest,
        *,
        request_id: str,
        tenant_id: str,
        sink: EventSink,
        user_id: str | None = None,
    ) -> IndexResult:
        started = time.perf_counter()
        timing = TimingCollector()
        await emit_simple(
            sink,
            request_id=request_id,
            stage="INDEX",
            event="index_started",
            message="INDEX request accepted",
            tenant_id=tenant_id,
            user_id=user_id,
            metadata={"document_id": request.document_id},
        )
        try:
            with stage_span("rag.index", tenant_id=tenant_id, document_id=request.document_id):
                result = await self._run(request, request_id, tenant_id, sink, timing, user_id)
            INDEX_REQUESTS.labels("success").inc()
            INDEX_DURATION.observe((time.perf_counter() - started))
            return result
        except Exception:
            INDEX_REQUESTS.labels("error").inc()
            self.status[make_document_key(tenant_id, request.document_id)] = IndexStatus(
                document_id=request.document_id,
                tenant_id=tenant_id,
                status="failed",
                error="indexing_failed",
                updated_at=datetime.now(UTC).isoformat(),
            )
            raise

    async def _run(
        self,
        request: IndexRequest,
        request_id: str,
        tenant_id: str,
        sink: EventSink,
        timing: TimingCollector,
        user_id: str | None,
    ) -> IndexResult:
        await emit_simple(
            sink,
            request_id=request_id,
            stage="VALIDATION",
            event="validating_document",
            message="Validating document",
            tenant_id=tenant_id,
        )
        if len(request.text) > self.settings.MAX_DOCUMENT_SIZE:
            raise ValidationAppError("Document exceeds MAX_DOCUMENT_SIZE")

        t0 = time.perf_counter()
        with stage_span("rag.document_clean"):
            cleaned = clean_document(request.text)
        timing.record("clean_ms", (time.perf_counter() - t0) * 1000)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="INDEX",
            event="document_cleaned",
            message="Cleaning document",
            duration_ms=timing.steps.get("clean_ms"),
            tenant_id=tenant_id,
        )

        t0 = time.perf_counter()
        await emit_simple(
            sink,
            request_id=request_id,
            stage="INDEX",
            event="chunking_started",
            message="Chunking started",
            tenant_id=tenant_id,
        )
        with stage_span("rag.chunk"):
            texts = with_title_prefix(
                chunk_text(
                    cleaned,
                    chunk_size=self.settings.CHUNK_SIZE,
                    chunk_overlap=self.settings.CHUNK_OVERLAP,
                ),
                extract_title(cleaned),
            )
        if not texts:
            raise ValidationAppError("Document produced no chunks")
        source = str(request.metadata.get("source") or request.document_id)
        ids = [
            make_chunk_id(
                tenant_id=tenant_id,
                document_id=request.document_id,
                document_version=request.document_version,
                chunk_index=i,
                content=text,
            )
            for i, text in enumerate(texts)
        ]
        chunks = build_chunks(
            texts=texts,
            tenant_id=tenant_id,
            document_id=request.document_id,
            document_version=request.document_version,
            source=source,
            metadata=request.metadata,
            chunk_ids=ids,
        )
        timing.record("chunk_ms", (time.perf_counter() - t0) * 1000)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="INDEX",
            event="chunks_created",
            message=f"Created {len(chunks)} chunks",
            duration_ms=timing.steps["chunk_ms"],
            tenant_id=tenant_id,
            metadata={"chunk_count": len(chunks)},
        )

        t0 = time.perf_counter()
        await self.bm25.delete_document(tenant_id, request.document_id)
        bm25_count = await self.bm25.upsert(chunks)
        timing.record("bm25_ms", (time.perf_counter() - t0) * 1000)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="BM25",
            event="bm25_update_completed",
            message=f"BM25 indexed {bm25_count} chunks",
            level="OK",
            duration_ms=timing.steps["bm25_ms"],
            tenant_id=tenant_id,
        )

        await self.vector_store.delete_document(tenant_id, request.document_id)
        embeddings = await self._embed_batches(chunks, sink, request_id, tenant_id, timing)

        t0 = time.perf_counter()
        with stage_span("rag.pinecone_upsert", chunk_count=len(chunks)):
            vectors_indexed = await retry_async(
                lambda: self.vector_store.upsert(chunks, embeddings),
                max_attempts=self.settings.MAX_RETRIES,
                timeout_seconds=self.settings.PINECONE_TIMEOUT_SECONDS,
                provider="pinecone",
                operation_name="upsert",
                emit=sink.emit,
                request_id=request_id,
                tenant_id=tenant_id,
            )
        timing.record("pinecone_upsert_ms", (time.perf_counter() - t0) * 1000)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="VECTOR",
            event="pinecone_upsert_completed",
            message=f"Pinecone upsert {vectors_indexed} vectors",
            level="OK",
            duration_ms=timing.steps["pinecone_upsert_ms"],
            tenant_id=tenant_id,
        )

        CHUNKS_INDEXED.inc(len(chunks))
        status = IndexStatus(
            document_id=request.document_id,
            tenant_id=tenant_id,
            status="completed",
            chunks_created=len(chunks),
            updated_at=datetime.now(UTC).isoformat(),
        )
        self.status[make_document_key(tenant_id, request.document_id)] = status
        await emit_simple(
            sink,
            request_id=request_id,
            stage="INDEX",
            event="index_complete",
            message="Index complete",
            level="DONE",
            duration_ms=timing.elapsed_ms(),
            tenant_id=tenant_id,
        )
        return IndexResult(
            request_id=request_id,
            document_id=request.document_id,
            chunks_created=len(chunks),
            vectors_indexed=vectors_indexed,
            bm25_documents_indexed=bm25_count,
            status="completed",
            timings=timing.as_dict(),
        )

    async def _embed_batches(
        self,
        chunks: list[Chunk],
        sink: EventSink,
        request_id: str,
        tenant_id: str,
        timing: TimingCollector,
    ) -> list[list[float]]:
        batch_size = 16
        vectors: list[list[float]] = []
        batches = [chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)]
        t0 = time.perf_counter()
        with stage_span("rag.embed_chunks", chunk_count=len(chunks)):
            for index, batch in enumerate(batches, start=1):
                await emit_simple(
                    sink,
                    request_id=request_id,
                    stage="EMBED",
                    event="embedding_batch",
                    message=f"Embedding batch {index}/{len(batches)}",
                    tenant_id=tenant_id,
                )
                texts = [f"source: {c.source}\n{c.text}" for c in batch]
                cached: list[list[float] | None] = []
                missing_idx: list[int] = []
                missing_texts: list[str] = []
                for i, text in enumerate(texts):
                    hit = await self.cache.embedding_lookup(text)
                    cached.append(hit)
                    if hit is None:
                        missing_idx.append(i)
                        missing_texts.append(text)
                computed: list[list[float]] = []
                if missing_texts:
                    async with self.limiter.limit_embedding():
                        computed = await self.embeddings.embed(missing_texts)
                    for text, vec in zip(missing_texts, computed, strict=True):
                        await self.cache.embedding_store(text, vec)
                computed_iter = iter(computed)
                batch_vectors: list[list[float]] = []
                for hit in cached:
                    if hit is None:
                        batch_vectors.append(next(computed_iter))
                    else:
                        batch_vectors.append(hit)
                vectors.extend(batch_vectors)
        timing.record("embedding_ms", (time.perf_counter() - t0) * 1000)
        return vectors

    async def delete(self, tenant_id: str, document_id: str) -> None:
        await self.vector_store.delete_document(tenant_id, document_id)
        await self.bm25.delete_document(tenant_id, document_id)
        self.status.pop(make_document_key(tenant_id, document_id), None)

    def get_status(self, tenant_id: str, document_id: str) -> IndexStatus | None:
        return self.status.get(make_document_key(tenant_id, document_id))
