"""Pinecone dense vector store with tenant metadata filter applied BEFORE results."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.config import Settings
from app.core.exceptions import VectorStoreUnavailable
from app.core.logging import get_logger
from app.models.document import Chunk, RetrievedChunk

logger = get_logger("rag.pinecone")


class PineconeVectorStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._index = None

    def _client(self):
        if self._index is not None:
            return self._index
        if not self._settings.PINECONE_API_KEY:
            raise VectorStoreUnavailable("PINECONE_API_KEY is not configured")
        from pinecone import Pinecone, ServerlessSpec

        pc = Pinecone(api_key=self._settings.PINECONE_API_KEY)
        name = self._settings.PINECONE_INDEX
        self._ensure_index(pc, ServerlessSpec, name)
        self._index = pc.Index(name)
        return self._index

    def _ensure_index(self, pc, serverless_spec, name: str) -> None:
        exists = False
        try:
            if hasattr(pc, "has_index"):
                exists = bool(pc.has_index(name))
            else:
                pc.describe_index(name)
                exists = True
        except Exception as exc:
            if type(exc).__name__ != "NotFoundError" and "404" not in str(exc):
                logger.warning("pinecone_describe_failed", index=name, error=type(exc).__name__)
            exists = False

        if not exists:
            logger.info(
                "pinecone_creating_index",
                index=name,
                dimension=self._settings.EMBEDDING_DIMENSION,
            )
            pc.create_index(
                name=name,
                dimension=self._settings.EMBEDDING_DIMENSION,
                metric="cosine",
                spec=serverless_spec(
                    cloud=self._settings.PINECONE_CLOUD,
                    region=self._settings.PINECONE_REGION,
                ),
            )

        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                desc = pc.describe_index(name)
                status = getattr(desc, "status", None)
                ready = False
                if status is None:
                    ready = True
                elif isinstance(status, dict):
                    ready = bool(status.get("ready", False))
                else:
                    ready = bool(getattr(status, "ready", False))
                if ready:
                    logger.info("pinecone_index_ready", index=name)
                    return
            except Exception:
                pass
            time.sleep(2)
        raise VectorStoreUnavailable(f"Pinecone index '{name}' was created but did not become ready")

    async def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        index = self._client()
        vectors = []
        for chunk, vector in zip(chunks, embeddings, strict=True):
            vectors.append(
                {
                    "id": chunk.chunk_id,
                    "values": vector,
                    "metadata": {
                        "tenant_id": chunk.tenant_id,
                        "document_id": chunk.document_id,
                        "document_version": chunk.document_version,
                        "chunk_index": chunk.chunk_index,
                        "source": chunk.source,
                        "text": chunk.text[:4000],
                        **{
                            k: v
                            for k, v in chunk.metadata.items()
                            if isinstance(v, (str, int, float, bool))
                        },
                    },
                }
            )
        await asyncio.to_thread(index.upsert, vectors=vectors)
        return len(vectors)

    async def search(
        self,
        embedding: list[float],
        *,
        tenant_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        index = self._client()
        pinecone_filter: dict[str, Any] = {"tenant_id": {"$eq": tenant_id}}
        if filters:
            for key, value in filters.items():
                if key == "tenant_id":
                    continue
                pinecone_filter[key] = {"$eq": value}

        try:
            result = await asyncio.to_thread(
                index.query,
                vector=embedding,
                top_k=top_k,
                filter=pinecone_filter,
                include_metadata=True,
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(str(type(exc).__name__)) from exc

        matches = getattr(result, "matches", None) or result.get("matches", [])
        retrieved: list[RetrievedChunk] = []
        for rank, match in enumerate(matches, start=1):
            meta = getattr(match, "metadata", None) or match.get("metadata") or {}
            if meta.get("tenant_id") != tenant_id:
                continue
            chunk = Chunk(
                chunk_id=getattr(match, "id", None) or match.get("id"),
                tenant_id=tenant_id,
                document_id=str(meta.get("document_id", "")),
                document_version=str(meta.get("document_version", "v1")),
                chunk_index=int(meta.get("chunk_index", 0)),
                source=str(meta.get("source", "")),
                text=str(meta.get("text", "")),
                metadata=dict(meta),
            )
            score = float(getattr(match, "score", None) or match.get("score") or 0.0)
            retrieved.append(
                RetrievedChunk(
                    chunk=chunk,
                    retrieval_score=score,
                    vector_rank=rank,
                    origin="vector",
                )
            )
        return retrieved

    async def delete_document(self, tenant_id: str, document_id: str) -> int:
        index = self._client()
        try:
            await asyncio.to_thread(
                index.delete,
                filter={"tenant_id": {"$eq": tenant_id}, "document_id": {"$eq": document_id}},
            )
        except Exception as exc:
            name = type(exc).__name__
            message = str(exc).lower()
            if name == "NotFoundError" or "404" in message or "namespace not found" in message:
                logger.info("pinecone_delete_skipped", reason=name, document_id=document_id)
                return 0
            raise VectorStoreUnavailable(name) from exc
        return 0

    async def ping(self) -> bool:
        try:
            self._client()
            return True
        except Exception:
            return False
