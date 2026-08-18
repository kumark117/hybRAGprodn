"""Deterministic chunk IDs.

Repeated indexing of the same tenant/document/version/content must not
silently create duplicate vectors. The ID is a hash of identity + content.
"""

from __future__ import annotations

import hashlib


def normalize_chunk_content(text: str) -> str:
    return " ".join(text.split())


def make_chunk_id(
    *,
    tenant_id: str,
    document_id: str,
    document_version: str,
    chunk_index: int,
    content: str,
) -> str:
    normalized = normalize_chunk_content(content)
    payload = (
        f"{tenant_id}|{document_id}|{document_version}|{chunk_index}|{normalized}"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"chk_{digest[:32]}"


def make_document_key(tenant_id: str, document_id: str) -> str:
    return f"{tenant_id}:{document_id}"
