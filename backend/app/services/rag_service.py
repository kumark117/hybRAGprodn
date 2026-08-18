"""RAG orchestrator — the pipeline is meant to be readable top-to-bottom.

REQUEST → AUTH → CACHE → REWRITE → EMBED → (VECTOR ∥ BM25) → RRF → DEDUP
       → RERANK → CONTEXT → PROMPT → LLM → VALIDATE → CACHE WRITE → DONE
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from app.cache.cache_service import CacheService
from app.core.circuit_breaker import CircuitBreaker
from app.core.config import Settings
from app.core.exceptions import CircuitOpenError, RetryableProviderError, ValidationAppError
from app.core.retry import retry_async
from app.core.security import Principal
from app.llm.fallback_provider import FallbackLLMProvider
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt, validate_answer
from app.llm.query_rewriter import QueryRewriter
from app.models.document import RetrievedChunk
from app.observability.event_bus import EventSink
from app.observability.metrics import (
    BM25_DURATION,
    CONTEXT_TOKENS,
    DEGRADED,
    REQUEST_DURATION,
    REQUESTS,
    RETRIEVAL_CANDIDATES,
    RRF_DURATION,
    VECTOR_DURATION,
)
from app.observability.timing import TimingCollector, emit_simple
from app.observability.tracing import current_trace_ids, stage_span
from app.retrieval.context_builder import ContextBuilder
from app.retrieval.dedup import deduplicate
from app.retrieval.fusion import boost_path_matches, preferred_sources, reciprocal_rank_fusion
from app.retrieval.reranker import LexicalOverlapReranker, Reranker
from app.schemas.query import DebugPayload, QueryRequest, QueryResponse, RAGMetadata, Source


class RAGService:
    def __init__(
        self,
        settings: Settings,
        embeddings,
        vector_store,
        bm25,
        reranker: Reranker,
        llm: FallbackLLMProvider,
        rewriter: QueryRewriter,
        cache: CacheService,
        context_builder: ContextBuilder,
        limiter,
        vector_circuit: CircuitBreaker,
        bm25_circuit: CircuitBreaker,
        rerank_circuit: CircuitBreaker,
    ) -> None:
        self.settings = settings
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.bm25 = bm25
        self.reranker = reranker
        self.llm = llm
        self.rewriter = rewriter
        self.cache = cache
        self.context_builder = context_builder
        self.limiter = limiter
        self.vector_circuit = vector_circuit
        self.bm25_circuit = bm25_circuit
        self.rerank_circuit = rerank_circuit

    async def query(
        self,
        request: QueryRequest,
        principal: Principal,
        sink: EventSink,
        *,
        request_id: str,
        stream: bool = False,
        on_token: Callable[[str], Awaitable[None]] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> QueryResponse:
        timing = TimingCollector()
        trace_id, _ = current_trace_ids()
        tenant_id = principal.tenant_id
        user_id = principal.user_id
        debug_allowed = request.debug and principal.role in {"admin", "analyst"}

        await emit_simple(
            sink,
            request_id=request_id,
            stage="REQUEST",
            event="request_received",
            message="Request received",
            tenant_id=tenant_id,
            user_id=user_id,
        )

        if len(request.query) > self.settings.MAX_QUERY_LENGTH:
            raise ValidationAppError("Query exceeds MAX_QUERY_LENGTH")

        await emit_simple(
            sink,
            request_id=request_id,
            stage="VALIDATION",
            event="request_validated",
            message="Query validated",
            tenant_id=tenant_id,
            user_id=user_id,
        )

        async with self.limiter.limit_query():
            with stage_span(
                "rag.query",
                tenant_id=tenant_id,
                retrieval_mode="hybrid",
            ):
                response = await self._run(
                    request=request,
                    principal=principal,
                    sink=sink,
                    request_id=request_id,
                    timing=timing,
                    stream=stream,
                    on_token=on_token,
                    cancel=cancel,
                    debug_allowed=debug_allowed,
                    trace_id=trace_id,
                )
        REQUEST_DURATION.observe(timing.elapsed_ms() / 1000)
        REQUESTS.labels(
            "success",
            response.metadata.retrieval_mode,
            "hit" if response.metadata.cache_hit else "miss",
        ).inc()
        return response

    async def _run(
        self,
        *,
        request: QueryRequest,
        principal: Principal,
        sink: EventSink,
        request_id: str,
        timing: TimingCollector,
        stream: bool,
        on_token,
        cancel,
        debug_allowed: bool,
        trace_id: str | None,
    ) -> QueryResponse:
        tenant_id = principal.tenant_id
        cache_key = self.cache.exact_key(
            tenant_id=tenant_id,
            query=request.query,
            filters=request.filters,
            llm_model=self.llm.primary.model,
        )

        cached = None
        if request.use_cache:
            with stage_span("rag.cache_lookup"):
                cached = await self.cache.lookup_exact(
                    key=cache_key,
                    sink=sink,
                    request_id=request_id,
                    tenant_id=tenant_id,
                )
        else:
            await emit_simple(
                sink,
                request_id=request_id,
                stage="CACHE",
                event="cache_skipped",
                message="Cache skipped (use_cache=false)",
                tenant_id=tenant_id,
            )
        if cached:
            meta = cached.get("metadata") or {}
            empty_hit = (
                not cached.get("sources")
                or int(meta.get("candidate_count") or 0) == 0
                or _insufficient_answer(str(cached.get("answer") or ""))
            )
            if empty_hit:
                await emit_simple(
                    sink,
                    request_id=request_id,
                    stage="CACHE",
                    event="cache_ignored",
                    message="Ignoring empty cached miss; retrieving again",
                    level="WARN",
                    tenant_id=tenant_id,
                )
                cached = None
        if cached:
            cached["request_id"] = request_id
            cached.setdefault("metadata", {})["cache_hit"] = True
            cached["metadata"]["latency_ms"] = timing.elapsed_ms()
            await emit_simple(
                sink,
                request_id=request_id,
                stage="COMPLETE",
                event="request_completed",
                message=f"Total: {timing.elapsed_ms():.0f} ms (cache hit)",
                level="DONE",
                duration_ms=timing.elapsed_ms(),
                tenant_id=tenant_id,
                metadata={"cache_hit": True},
            )
            return QueryResponse.model_validate(cached)

        rewrite_enabled = self.settings.REWRITE_ENABLED if request.rewrite is None else request.rewrite
        rewritten = request.query
        if rewrite_enabled:
            t0 = time.perf_counter()
            with stage_span("rag.query_rewrite"):
                rewritten = await self.rewriter.rewrite(
                    request.query,
                    sink=sink,
                    request_id=request_id,
                    tenant_id=tenant_id,
                    debug=debug_allowed,
                )
            timing.record("rewrite_ms", (time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        await emit_simple(
            sink,
            request_id=request_id,
            stage="EMBED",
            event="embed_started",
            message="Embedding query",
            tenant_id=tenant_id,
        )
        with stage_span("rag.embed_query"):
            query_vector = await self._embed_query(rewritten, sink, request_id, tenant_id)
        timing.record("embedding_ms", (time.perf_counter() - t0) * 1000)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="EMBED",
            event="embed_completed",
            message=f"Embedded ({timing.steps['embedding_ms']:.0f} ms)",
            level="OK",
            duration_ms=timing.steps["embedding_ms"],
            tenant_id=tenant_id,
        )

        vector_results, bm25_results, retrieval_mode, degraded = await self._retrieve_parallel(
            query=rewritten,
            query_vector=query_vector,
            tenant_id=tenant_id,
            filters=request.filters,
            sink=sink,
            request_id=request_id,
            timing=timing,
        )

        fused: list[RetrievedChunk] = []
        if vector_results and bm25_results:
            t0 = time.perf_counter()
            await emit_simple(
                sink,
                request_id=request_id,
                stage="RRF",
                event="rrf_started",
                message="Combining ranked lists",
                level="START",
                tenant_id=tenant_id,
            )
            with stage_span("rag.fusion.rrf"):
                fused = reciprocal_rank_fusion(
                    {"vector": vector_results, "bm25": bm25_results},
                    k=self.settings.RRF_K,
                )
            timing.record("rrf_ms", (time.perf_counter() - t0) * 1000)
            RRF_DURATION.observe(timing.steps["rrf_ms"] / 1000)
            await emit_simple(
                sink,
                request_id=request_id,
                stage="RRF",
                event="rrf_completed",
                message=f"{len(fused)} unique candidates ({timing.steps['rrf_ms']:.0f} ms)",
                level="OK",
                duration_ms=timing.steps["rrf_ms"],
                tenant_id=tenant_id,
                metadata={"candidate_count": len(fused)},
            )
        else:
            fused = vector_results or bm25_results
            await emit_simple(
                sink,
                request_id=request_id,
                stage="RRF",
                event="rrf_skipped",
                message="RRF skipped / single ranked list",
                level="WARN",
                tenant_id=tenant_id,
            )

        t0 = time.perf_counter()
        with stage_span("rag.deduplicate"):
            unique = boost_path_matches(rewritten, deduplicate(fused))
        timing.record("dedup_ms", (time.perf_counter() - t0) * 1000)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="DEDUP",
            event="dedup_completed",
            message=f"{len(unique)} after dedup",
            level="OK",
            duration_ms=timing.steps["dedup_ms"],
            tenant_id=tenant_id,
        )
        RETRIEVAL_CANDIDATES.observe(len(unique))

        named = preferred_sources(rewritten, unique)
        rerank_k = self.settings.RERANK_TOP_K
        if named:
            rerank_k = max(rerank_k, request.top_k, 12)
        reranked = await self._rerank(
            query=rewritten,
            candidates=unique[:30],
            top_k=min(rerank_k, 20),
            sink=sink,
            request_id=request_id,
            tenant_id=tenant_id,
            timing=timing,
        )

        await emit_simple(
            sink,
            request_id=request_id,
            stage="CONTEXT",
            event="context_started",
            message="Building context",
            tenant_id=tenant_id,
        )
        t0 = time.perf_counter()
        with stage_span("rag.context_build"):
            context = self.context_builder.build(reranked, preferred_sources=named)
        timing.record("context_ms", (time.perf_counter() - t0) * 1000)
        CONTEXT_TOKENS.observe(context.token_count)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="CONTEXT",
            event="context_completed",
            message=f"{context.token_count:,} tokens",
            level="OK",
            duration_ms=timing.steps["context_ms"],
            tenant_id=tenant_id,
            metadata={
                "context_candidates": context.candidates_in,
                "context_selected": len(context.chunks),
                "context_tokens": context.token_count,
                "documents_represented": context.documents_represented,
            },
        )

        t0 = time.perf_counter()
        with stage_span("rag.prompt_build"):
            user_prompt = build_user_prompt(rewritten, context.chunks)
        timing.record("prompt_ms", (time.perf_counter() - t0) * 1000)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="PROMPT",
            event="prompt_built",
            message="Prompt built",
            level="OK",
            duration_ms=timing.steps["prompt_ms"],
            tenant_id=tenant_id,
        )

        await emit_simple(
            sink,
            request_id=request_id,
            stage="LLM",
            event="llm_started",
            message="Generation started",
            level="START",
            tenant_id=tenant_id,
        )
        t0 = time.perf_counter()
        with stage_span("rag.llm_generate", model_name=self.llm.primary.model):
            if stream:
                llm_result = await self.llm.stream(
                    system=SYSTEM_PROMPT,
                    user=user_prompt,
                    sink=sink,
                    request_id=request_id,
                    tenant_id=tenant_id,
                    on_token=on_token,
                    cancel=cancel,
                )
            else:
                llm_result = await self.llm.generate(
                    system=SYSTEM_PROMPT,
                    user=user_prompt,
                    sink=sink,
                    request_id=request_id,
                    tenant_id=tenant_id,
                )
        timing.record("llm_total_ms", (time.perf_counter() - t0) * 1000)
        if llm_result.time_to_first_token_ms is not None:
            timing.record("llm_first_token_ms", llm_result.time_to_first_token_ms)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="LLM",
            event="llm_completed",
            message="Generation complete",
            level="OK",
            duration_ms=timing.steps["llm_total_ms"],
            tenant_id=tenant_id,
            metadata={"model": llm_result.model, "fallback_used": llm_result.fallback_used},
        )

        answer = validate_answer(llm_result.text)
        sources = _to_sources(context.chunks)
        metadata = RAGMetadata(
            cache_hit=False,
            fallback_used=llm_result.fallback_used,
            degraded_mode=degraded,
            retrieval_mode=retrieval_mode,
            candidate_count=len(unique),
            context_chunk_count=len(context.chunks),
            time_to_first_token_ms=llm_result.time_to_first_token_ms,
            latency_ms=timing.elapsed_ms(),
            llm_model=llm_result.model,
            rewritten_query=rewritten if debug_allowed else None,
            timings=timing.as_dict(),
            trace_id=trace_id,
        )
        debug_payload = None
        if debug_allowed:
            debug_payload = DebugPayload(
                original_query=request.query,
                rewritten_query=rewritten,
                vector_candidates=[c.debug_dict() for c in vector_results],
                bm25_candidates=[c.debug_dict() for c in bm25_results],
                rrf_results=[c.debug_dict() for c in fused[:20]],
                reranked=[c.debug_dict() for c in reranked],
                context_chunks=[c.debug_dict() for c in context.chunks],
                timings=timing.as_dict(),
                cache_hit=False,
                fallback_used=llm_result.fallback_used,
                retrieval_mode=retrieval_mode,
            )

        response = QueryResponse(
            request_id=request_id,
            trace_id=trace_id,
            answer=answer,
            sources=sources,
            metadata=metadata,
            debug=debug_payload,
        )

        if request.use_cache and context.chunks and not _insufficient_answer(answer):
            t0 = time.perf_counter()
            with stage_span("rag.cache_write"):
                await self.cache.write_exact(
                    key=cache_key,
                    payload=response.model_dump(mode="json"),
                    sink=sink,
                    request_id=request_id,
                    tenant_id=tenant_id,
                )
            timing.record("cache_write_ms", (time.perf_counter() - t0) * 1000)
            response.metadata.timings = timing.as_dict()
            response.metadata.latency_ms = timing.elapsed_ms()

        await emit_simple(
            sink,
            request_id=request_id,
            stage="COMPLETE",
            event="request_completed",
            message=f"Total: {timing.elapsed_ms():,.0f} ms",
            level="DONE",
            duration_ms=timing.elapsed_ms(),
            tenant_id=tenant_id,
            metadata={
                "retrieval_mode": retrieval_mode,
                "degraded_mode": degraded,
                "cache_hit": False,
            },
        )
        return response

    async def _embed_query(
        self, query: str, sink: EventSink, request_id: str, tenant_id: str
    ) -> list[float]:
        cached = await self.cache.embedding_lookup(query)
        if cached:
            return cached
        async with self.limiter.limit_embedding():
            vectors = await retry_async(
                lambda: self.embeddings.embed([query]),
                max_attempts=self.settings.MAX_RETRIES,
                timeout_seconds=self.settings.EMBEDDING_TIMEOUT_SECONDS,
                provider="embedding",
                operation_name="embed_query",
                emit=sink.emit,
                request_id=request_id,
                tenant_id=tenant_id,
            )
        vector = vectors[0]
        await self.cache.embedding_store(query, vector)
        return vector

    async def _retrieve_parallel(
        self,
        *,
        query: str,
        query_vector: list[float],
        tenant_id: str,
        filters: dict[str, Any],
        sink: EventSink,
        request_id: str,
        timing: TimingCollector,
    ) -> tuple[list[RetrievedChunk], list[RetrievedChunk], Literal["hybrid", "vector_only", "bm25_only", "none"], bool]:
        await emit_simple(
            sink,
            request_id=request_id,
            stage="VECTOR",
            event="vector_started",
            message="Pinecone retrieval started",
            level="START",
            tenant_id=tenant_id,
        )
        await emit_simple(
            sink,
            request_id=request_id,
            stage="BM25",
            event="bm25_started",
            message="BM25 retrieval started",
            level="START",
            tenant_id=tenant_id,
        )

        async def vector_search() -> list[RetrievedChunk]:
            t0 = time.perf_counter()
            with stage_span("rag.retrieve.vector"):
                result = await self.vector_circuit.call(
                    lambda: retry_async(
                        lambda: self.vector_store.search(
                            query_vector,
                            tenant_id=tenant_id,
                            top_k=self.settings.VECTOR_TOP_K,
                            filters=filters,
                        ),
                        max_attempts=self.settings.MAX_RETRIES,
                        timeout_seconds=self.settings.PINECONE_TIMEOUT_SECONDS,
                        provider="pinecone",
                        operation_name="search",
                        emit=sink.emit,
                        request_id=request_id,
                        tenant_id=tenant_id,
                    ),
                    emit=sink.emit,
                    request_id=request_id,
                    tenant_id=tenant_id,
                )
            duration = (time.perf_counter() - t0) * 1000
            timing.record("pinecone_ms", duration)
            VECTOR_DURATION.observe(duration / 1000)
            await emit_simple(
                sink,
                request_id=request_id,
                stage="VECTOR",
                event="vector_completed",
                message=f"{len(result)} candidates ({duration:.0f} ms)",
                level="OK",
                duration_ms=duration,
                tenant_id=tenant_id,
                metadata={"candidate_count": len(result)},
            )
            return result

        async def bm25_search() -> list[RetrievedChunk]:
            t0 = time.perf_counter()
            with stage_span("rag.retrieve.bm25"):
                result = await self.bm25_circuit.call(
                    lambda: retry_async(
                        lambda: self.bm25.search(
                            query,
                            tenant_id=tenant_id,
                            top_k=self.settings.BM25_TOP_K,
                            filters=filters,
                        ),
                        max_attempts=self.settings.MAX_RETRIES,
                        timeout_seconds=2.0,
                        provider="bm25",
                        operation_name="search",
                        emit=sink.emit,
                        request_id=request_id,
                        tenant_id=tenant_id,
                    ),
                    emit=sink.emit,
                    request_id=request_id,
                    tenant_id=tenant_id,
                )
            duration = (time.perf_counter() - t0) * 1000
            timing.record("bm25_ms", duration)
            BM25_DURATION.observe(duration / 1000)
            await emit_simple(
                sink,
                request_id=request_id,
                stage="BM25",
                event="bm25_completed",
                message=f"{len(result)} candidates ({duration:.0f} ms)",
                level="OK",
                duration_ms=duration,
                tenant_id=tenant_id,
                metadata={"candidate_count": len(result)},
            )
            return result

        vector_outcome, bm25_outcome = await asyncio.gather(
            vector_search(),
            bm25_search(),
            return_exceptions=True,
        )

        vector_results: list[RetrievedChunk] = []
        bm25_results: list[RetrievedChunk] = []
        if isinstance(vector_outcome, Exception):
            await emit_simple(
                sink,
                request_id=request_id,
                stage="RETRIEVAL",
                event="vector_degraded",
                message="Falling back to BM25-only",
                level="WARN",
                tenant_id=tenant_id,
                metadata={"error_type": type(vector_outcome).__name__},
            )
        else:
            vector_results = vector_outcome
        if isinstance(bm25_outcome, Exception):
            await emit_simple(
                sink,
                request_id=request_id,
                stage="RETRIEVAL",
                event="bm25_degraded",
                message="Falling back to vector-only",
                level="WARN",
                tenant_id=tenant_id,
                metadata={"error_type": type(bm25_outcome).__name__},
            )
        else:
            bm25_results = bm25_outcome

        vector_ok = not isinstance(vector_outcome, Exception)
        bm25_ok = not isinstance(bm25_outcome, Exception)
        if vector_ok and bm25_ok:
            mode: Literal["hybrid", "vector_only", "bm25_only", "none"] = "hybrid"
            degraded = False
        elif vector_ok:
            mode = "vector_only"
            degraded = True
        elif bm25_ok:
            mode = "bm25_only"
            degraded = True
        else:
            mode = "none"
            degraded = True

        if degraded:
            DEGRADED.labels(mode).inc()
            await emit_simple(
                sink,
                request_id=request_id,
                stage="MODE",
                event="degraded_mode",
                message=f"degraded_mode=true retrieval_mode={mode}",
                level="INFO",
                tenant_id=tenant_id,
                metadata={"retrieval_mode": mode, "degraded_mode": True},
            )
        return vector_results, bm25_results, mode, degraded

    async def _rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
        sink: EventSink,
        request_id: str,
        tenant_id: str,
        timing: TimingCollector,
    ) -> list[RetrievedChunk]:
        if not candidates:
            return []
        await emit_simple(
            sink,
            request_id=request_id,
            stage="RERANK",
            event="rerank_started",
            message="Cross-encoder reranking",
            level="START",
            tenant_id=tenant_id,
            metadata={"input_candidates": len(candidates)},
        )
        t0 = time.perf_counter()
        try:
            with stage_span("rag.rerank", candidate_count=len(candidates)):

                async def _call() -> list[RetrievedChunk]:
                    async with self.limiter.limit_rerank():
                        return await self.reranker.rerank(query, candidates, top_k=top_k)

                reranked = await self.rerank_circuit.call(
                    lambda: retry_async(
                        _call,
                        max_attempts=self.settings.MAX_RETRIES,
                        timeout_seconds=self.settings.RERANKER_TIMEOUT_SECONDS,
                        provider="reranker",
                        operation_name="rerank",
                        emit=sink.emit,
                        request_id=request_id,
                        tenant_id=tenant_id,
                    ),
                    emit=sink.emit,
                    request_id=request_id,
                    tenant_id=tenant_id,
                )
        except (RetryableProviderError, CircuitOpenError, Exception):
            duration = (time.perf_counter() - t0) * 1000
            timing.record("rerank_ms", duration)
            fallback = await LexicalOverlapReranker().rerank(query, candidates, top_k=top_k)
            await emit_simple(
                sink,
                request_id=request_id,
                stage="RERANK",
                event="rerank_fallback",
                message="Reranker failed; using lexical overlap",
                level="WARN",
                duration_ms=duration,
                tenant_id=tenant_id,
            )
            return fallback
        duration = (time.perf_counter() - t0) * 1000
        timing.record("rerank_ms", duration)
        await emit_simple(
            sink,
            request_id=request_id,
            stage="RERANK",
            event="rerank_completed",
            message=f"Selected {len(reranked)} chunks ({duration:.0f} ms)",
            level="OK",
            duration_ms=duration,
            tenant_id=tenant_id,
            metadata={
                "input_candidates": len(candidates),
                "output_candidates": len(reranked),
            },
        )
        return reranked


def _insufficient_answer(answer: str) -> bool:
    return "not enough evidence" in answer.lower()


def _to_sources(chunks: list[RetrievedChunk]) -> list[Source]:
    sources: list[Source] = []
    for index, item in enumerate(chunks, start=1):
        sources.append(
            Source(
                citation_id=index,
                document_id=item.chunk.document_id,
                chunk_id=item.chunk.chunk_id,
                source=item.chunk.source or item.chunk.document_id,
                retrieval_score=item.retrieval_score,
                rrf_score=item.rrf_score,
                reranker_score=item.reranker_score,
                text_preview=item.chunk.text[:240],
            )
        )
    return sources
