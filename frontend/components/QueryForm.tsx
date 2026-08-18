"use client";

export function QueryForm({
  query,
  setQuery,
  streaming,
  debug,
  setStreaming,
  setDebug,
  busy,
  onAsk,
  onStop,
}: {
  query: string;
  setQuery: (value: string) => void;
  streaming: boolean;
  debug: boolean;
  setStreaming: (value: boolean) => void;
  setDebug: (value: boolean) => void;
  busy: boolean;
  onAsk: () => void;
  onStop: () => void;
}) {
  return (
    <section className="card">
      <h2>Query</h2>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="How does the system handle retries?"
      />
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn" type="button" onClick={onAsk} disabled={busy || !query.trim()}>
          Ask
        </button>
        <button className="btn danger" type="button" onClick={onStop} disabled={!busy}>
          Stop
        </button>
        <label style={{ display: "flex", gap: 6, alignItems: "center", textTransform: "none" }}>
          <input type="checkbox" checked={streaming} onChange={(e) => setStreaming(e.target.checked)} />
          Stream
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center", textTransform: "none" }}>
          <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} />
          Debug
        </label>
      </div>
    </section>
  );
}
