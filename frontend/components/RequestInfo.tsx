"use client";

import type { RAGMetadata } from "@/lib/types";

export function RequestInfo({
  requestId,
  metadata,
}: {
  requestId: string;
  metadata: RAGMetadata | null;
}) {
  return (
    <section className="card">
      <h2>Request info</h2>
      <div className="meta-grid">
        <span>request_id</span>
        <div>{requestId || "—"}</div>
        <span>trace_id</span>
        <div>{metadata?.trace_id || "—"}</div>
        <span>retrieval</span>
        <div>{metadata?.retrieval_mode || "—"}</div>
        <span>cache</span>
        <div>{metadata ? (metadata.cache_hit ? "hit" : "miss") : "—"}</div>
        <span>fallback</span>
        <div>{metadata?.fallback_used ? "yes" : "no"}</div>
        <span>degraded</span>
        <div>{metadata?.degraded_mode ? "yes" : "no"}</div>
        <span>candidates</span>
        <div>{metadata?.candidate_count ?? "—"}</div>
        <span>context chunks</span>
        <div>{metadata?.context_chunk_count ?? "—"}</div>
        <span>TTFT</span>
        <div>{metadata?.time_to_first_token_ms != null ? `${Math.round(metadata.time_to_first_token_ms)} ms` : "—"}</div>
        <span>total</span>
        <div>{metadata?.latency_ms ? `${Math.round(metadata.latency_ms)} ms` : "—"}</div>
        <span>model</span>
        <div>{metadata?.llm_model || "—"}</div>
      </div>
    </section>
  );
}
