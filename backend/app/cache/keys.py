from __future__ import annotations

import hashlib
import json
from typing import Any


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def embedding_key(text: str, model: str, version: str) -> str:
    return f"emb:{_hash(f'{model}|{version}|{text}')}"


def exact_query_key(
    *,
    tenant_id: str,
    normalized_query: str,
    filters: dict[str, Any],
    llm_model: str,
    embedding_model: str,
    prompt_version: str,
    index_version: str,
    retrieval_config: str,
) -> str:
    blob = json.dumps(
        {
            "tenant": tenant_id,
            "q": normalized_query,
            "filters": filters,
            "llm": llm_model,
            "emb": embedding_model,
            "prompt": prompt_version,
            "index": index_version,
            "cfg": retrieval_config,
        },
        sort_keys=True,
    )
    return f"qexact:{tenant_id}:{_hash(blob)}"


def semantic_cache_index_key(tenant_id: str) -> str:
    return f"qsem:{tenant_id}:index"
