"""Application container — wires real or fake providers based on settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.cache.cache_service import CacheService, InMemoryCache, RedisCache
from app.cache.redis_client import create_redis
from app.core.circuit_breaker import CircuitBreaker
from app.core.concurrency import ConcurrencyLimiter
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.llm.embeddings import HashEmbeddingProvider, OpenAIEmbeddingProvider
from app.llm.fallback_provider import FallbackLLMProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.query_rewriter import QueryRewriter
from app.observability.event_bus import CompositeEventSink
from app.observability.logging_sink import StructuredLogSink
from app.observability.metrics import MetricsSink
from app.retrieval.bm25_store import BM25Store
from app.retrieval.context_builder import ContextBuilder
from app.retrieval.memory_store import InMemoryVectorStore
from app.retrieval.pinecone_store import PineconeVectorStore
from app.retrieval.reranker import LexicalOverlapReranker, LocalCrossEncoderReranker
from app.services.auth_service import AuthService
from app.services.indexing_service import IndexingService
from app.services.rag_service import RAGService


@dataclass
class AppContainer:
    settings: Settings
    redis: Any
    cache: CacheService
    limiter: ConcurrencyLimiter
    rate_limiter: RateLimiter
    vector_store: Any
    bm25: BM25Store
    rag: RAGService
    indexing: IndexingService
    auth: AuthService
    log_sink: StructuredLogSink
    metrics_sink: MetricsSink
    vector_circuit: CircuitBreaker
    bm25_circuit: CircuitBreaker
    llm_circuit: CircuitBreaker
    rerank_circuit: CircuitBreaker

    def base_sink(self) -> CompositeEventSink:
        return CompositeEventSink([self.log_sink, self.metrics_sink])


async def build_container(settings: Settings) -> AppContainer:
    redis = await create_redis(settings)
    cache_backend = RedisCache(redis) if redis is not None else InMemoryCache()
    cache = CacheService(cache_backend, settings, fail_open=settings.CACHE_FAIL_OPEN, redis_client=redis)
    limiter = ConcurrencyLimiter(
        llm=settings.MAX_LLM_CONCURRENCY,
        embedding=settings.MAX_EMBEDDING_CONCURRENCY,
        rerank=settings.MAX_RERANK_CONCURRENCY,
    )
    rate_limiter = RateLimiter(
        redis,
        per_user_per_minute=settings.RATE_LIMIT_PER_USER_PER_MINUTE,
        per_tenant_per_minute=settings.RATE_LIMIT_PER_TENANT_PER_MINUTE,
    )

    use_fakes = settings.USE_FAKE_PROVIDERS or not settings.OPENAI_API_KEY
    if use_fakes:
        embeddings = HashEmbeddingProvider(dimension=64)
        primary = MockLLMProvider("mock-primary")
        fallback = MockLLMProvider("mock-fallback")
        vector_store = InMemoryVectorStore()
        reranker = LexicalOverlapReranker()
    else:
        embeddings = OpenAIEmbeddingProvider(settings)
        primary = OpenAIProvider(settings, model=settings.OPENAI_MODEL, name="openai-primary")
        fallback = OpenAIProvider(settings, model=settings.OPENAI_FALLBACK_MODEL, name="openai-fallback")
        vector_store = (
            InMemoryVectorStore()
            if not settings.PINECONE_API_KEY
            else PineconeVectorStore(settings)
        )
        try:
            import sentence_transformers  # noqa: F401

            reranker = LocalCrossEncoderReranker()
        except Exception:
            reranker = LexicalOverlapReranker()

    bm25 = BM25Store()
    vector_circuit = CircuitBreaker(
        "pinecone",
        failure_threshold=settings.CIRCUIT_FAILURE_THRESHOLD,
        reset_seconds=settings.CIRCUIT_RESET_SECONDS,
        stage="VECTOR",
    )
    bm25_circuit = CircuitBreaker(
        "bm25",
        failure_threshold=settings.CIRCUIT_FAILURE_THRESHOLD,
        reset_seconds=settings.CIRCUIT_RESET_SECONDS,
        stage="BM25",
    )
    llm_circuit = CircuitBreaker(
        "llm",
        failure_threshold=settings.CIRCUIT_FAILURE_THRESHOLD,
        reset_seconds=settings.CIRCUIT_RESET_SECONDS,
        stage="LLM",
    )
    rerank_circuit = CircuitBreaker(
        "reranker",
        failure_threshold=settings.CIRCUIT_FAILURE_THRESHOLD,
        reset_seconds=settings.CIRCUIT_RESET_SECONDS,
        stage="RERANK",
    )
    llm = FallbackLLMProvider(primary, fallback, settings, llm_circuit, limiter)
    rewriter = QueryRewriter(primary if settings.REWRITE_ENABLED else None, enabled=settings.REWRITE_ENABLED)
    context_builder = ContextBuilder(settings.MAX_CONTEXT_TOKENS, settings.MAX_CHUNKS_PER_SOURCE)
    rag = RAGService(
        settings=settings,
        embeddings=embeddings,
        vector_store=vector_store,
        bm25=bm25,
        reranker=reranker,
        llm=llm,
        rewriter=rewriter,
        cache=cache,
        context_builder=context_builder,
        limiter=limiter,
        vector_circuit=vector_circuit,
        bm25_circuit=bm25_circuit,
        rerank_circuit=rerank_circuit,
    )
    indexing = IndexingService(
        settings=settings,
        embeddings=embeddings,
        vector_store=vector_store,
        bm25=bm25,
        limiter=limiter,
        cache=cache,
    )
    return AppContainer(
        settings=settings,
        redis=redis,
        cache=cache,
        limiter=limiter,
        rate_limiter=rate_limiter,
        vector_store=vector_store,
        bm25=bm25,
        rag=rag,
        indexing=indexing,
        auth=AuthService(settings),
        log_sink=StructuredLogSink(),
        metrics_sink=MetricsSink(),
        vector_circuit=vector_circuit,
        bm25_circuit=bm25_circuit,
        llm_circuit=llm_circuit,
        rerank_circuit=rerank_circuit,
    )
