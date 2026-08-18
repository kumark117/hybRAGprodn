"""Optional conversational query rewrite.

Only rewrite when the query looks underspecified (pronouns / follow-ups).
Never log the full query unless debug mode is on.
"""

from __future__ import annotations

import re

from app.llm.base import LLMProvider
from app.observability.event_bus import EventSink
from app.observability.timing import emit_simple

_FOLLOWUP = re.compile(
    r"\b(it|its|this|that|they|them|those|these|the system|what about|and how)\b",
    re.IGNORECASE,
)


class QueryRewriter:
    def __init__(self, llm: LLMProvider | None, enabled: bool = True) -> None:
        self._llm = llm
        self.enabled = enabled

    async def rewrite(
        self,
        query: str,
        *,
        sink: EventSink,
        request_id: str,
        tenant_id: str | None,
        debug: bool,
    ) -> str:
        if not self.enabled or self._llm is None or not _FOLLOWUP.search(query):
            return query

        await emit_simple(
            sink,
            request_id=request_id,
            stage="REWRITE",
            event="query_rewrite_started",
            message="Rewriting query",
            tenant_id=tenant_id,
        )
        system = (
            "Rewrite the user question into a standalone search query. "
            "Do not answer it. Return only the rewritten query."
        )
        try:
            result = await self._llm.generate(system=system, user=query)
            rewritten = (result.text or query).strip().splitlines()[0]
            await emit_simple(
                sink,
                request_id=request_id,
                stage="REWRITE",
                event="query_rewrite_completed",
                message="Completed",
                level="OK",
                tenant_id=tenant_id,
                metadata={"rewritten": rewritten if debug else None},
            )
            return rewritten or query
        except Exception:
            await emit_simple(
                sink,
                request_id=request_id,
                stage="REWRITE",
                event="query_rewrite_failed",
                message="Rewrite failed; using original query",
                level="WARN",
                tenant_id=tenant_id,
            )
            return query
