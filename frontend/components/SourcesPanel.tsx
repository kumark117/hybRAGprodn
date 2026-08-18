"use client";

import type { Source } from "@/lib/types";

export function SourcesPanel({ sources }: { sources: Source[] }) {
  return (
    <section className="card">
      <h2>Sources</h2>
      {sources.length === 0 ? (
        <div style={{ color: "var(--muted)" }}>No citations yet.</div>
      ) : (
        sources.map((source) => (
          <div className="source-item" key={`${source.citation_id}-${source.chunk_id}`}>
            <strong>[{source.citation_id}]</strong> {source.source || source.document_id}
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              rrf={source.rrf_score?.toFixed(4) ?? "—"} rerank={source.reranker_score?.toFixed(3) ?? "—"}
            </div>
          </div>
        ))
      )}
    </section>
  );
}
