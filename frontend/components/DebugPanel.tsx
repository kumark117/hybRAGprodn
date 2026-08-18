"use client";

import type { RAGMetadata } from "@/lib/types";

export function DebugPanel({ metadata, extra }: { metadata: RAGMetadata | null; extra: unknown }) {
  if (!metadata && !extra) return null;
  return (
    <section className="card" style={{ marginTop: 16 }}>
      <h2>Debug timings</h2>
      <pre style={{ overflow: "auto", fontSize: 12, color: "var(--muted)" }}>
        {JSON.stringify({ timings: metadata?.timings, extra }, null, 2)}
      </pre>
    </section>
  );
}
