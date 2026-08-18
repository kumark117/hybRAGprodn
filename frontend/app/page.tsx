import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>Production hybrid RAG</h1>
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Dense Pinecone retrieval and BM25 lexical search run in parallel, fuse with Reciprocal Rank
        Fusion, rerank, then generate with citations. Every stage emits structured logs, Prometheus
        metrics, optional OpenTelemetry traces, and live SSE events to the Log Pane.
      </p>
      <div className="grid-2" style={{ marginTop: 24 }}>
        <section className="card">
          <h2>Query</h2>
          <p>Stream an answer and watch CACHE → VECTOR ∥ BM25 → RRF → RERANK → LLM live.</p>
          <p>
            <Link href="/query">Open query console →</Link>
          </p>
        </section>
        <section className="card">
          <h2>Index</h2>
          <p>Chunk, embed, upsert to the vector store and BM25, with a scrolling index log.</p>
          <p>
            <Link href="/indexing">Open indexer →</Link>
          </p>
        </section>
      </div>
      <section className="card" style={{ marginTop: 16 }}>
        <h2>Demo login</h2>
        <p>
          <code>analyst</code> / <code>analystpass</code> → tenant-a
          <br />
          <code>other</code> / <code>otherpass</code> → tenant-b
        </p>
      </section>
    </main>
  );
}
