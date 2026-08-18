"""Vector store interface. Pinecone is one implementation; tests use an in-memory fake."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.models.document import Chunk, RetrievedChunk


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(self, chunks: list[Chunk], embeddings: list[list[float]]) -> int: ...

    async def search(
        self,
        embedding: list[float],
        *,
        tenant_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]: ...

    async def delete_document(self, tenant_id: str, document_id: str) -> int: ...

    async def ping(self) -> bool: ...
