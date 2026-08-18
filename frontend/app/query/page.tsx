"use client";

import dynamic from "next/dynamic";
import { useMemo, useRef, useState } from "react";
import { login, streamQuery } from "@/lib/api";
import { appendLog } from "@/lib/logStore";
import type { LogEvent, RAGMetadata, Source } from "@/lib/types";
import { AnswerPanel } from "@/components/AnswerPanel";
import { DebugPanel } from "@/components/DebugPanel";
import { QueryForm } from "@/components/QueryForm";
import { RequestInfo } from "@/components/RequestInfo";
import { SourcesPanel } from "@/components/SourcesPanel";
const LogPane = dynamic(() => import("@/components/LogPane").then((m) => m.LogPane), {
  ssr: false,
  loading: () => null,
});

const SESSION_KEY = "rag.token";

export default function QueryPage() {
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("analystpass");
  const [token, setToken] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return window.localStorage.getItem(SESSION_KEY) ?? "";
  });
  const [tenantId, setTenantId] = useState("tenant-a");
  const [query, setQuery] = useState("How does the system handle retries?");
  const [streaming, setStreaming] = useState(true);
  const [debug, setDebug] = useState(true);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState("");
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [metadata, setMetadata] = useState<RAGMetadata | null>(null);
  const [requestId, setRequestId] = useState("");
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const logBuffer = useRef<LogEvent[]>([]);
  const flushTimer = useRef<number | null>(null);

  const session = useMemo(() => Boolean(token), [token]);

  function enqueueLogs(event: LogEvent) {
    logBuffer.current.push(event);
    if (flushTimer.current != null) return;
    flushTimer.current = window.setTimeout(() => {
      const batch = logBuffer.current;
      logBuffer.current = [];
      flushTimer.current = null;
      setLogs((prev) => appendLog(prev, batch));
    }, 40);
  }

  async function handleLogin() {
    const result = await login(username, password);
    setToken(result.access_token);
    setTenantId(result.tenant_id);
    window.localStorage.setItem(SESSION_KEY, result.access_token);
  }

  async function handleAsk() {
    if (!token) {
      setError("Login first");
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setAnswer("");
    setSources([]);
    setMetadata(null);
    setError("");
    setLogs([]);
    const showStream = streaming;
    let buffered = "";
    try {
      await streamQuery(
        token,
        {
          query,
          tenant_id: tenantId,
          use_cache: true,
          debug,
        },
        {
          onLog: (event) => {
            enqueueLogs(event);
            if (event.requestId) setRequestId(event.requestId);
          },
          onToken: (event) => {
            buffered += event.text;
            if (showStream) setAnswer((prev) => prev + event.text);
            if (event.requestId) setRequestId(event.requestId);
          },
          onCitation: (event) => {
            setSources((prev) => {
              const next: Source = {
                citation_id: Number(event.citation_id ?? prev.length + 1),
                document_id: String(event.document_id ?? ""),
                chunk_id: String(event.chunk_id ?? ""),
                source: String(event.source ?? ""),
                retrieval_score: event.retrieval_score,
                rrf_score: event.rrf_score,
                reranker_score: event.reranker_score,
                text_preview: event.text_preview,
              };
              if (prev.some((item) => item.chunk_id === next.chunk_id)) return prev;
              return [...prev, next];
            });
          },
          onMetadata: (meta) => setMetadata(meta),
          onError: (event) => setError(event.message),
          onDone: (event) => {
            const finalAnswer = event.answer || buffered;
            if (finalAnswer) setAnswer(finalAnswer);
            setBusy(false);
          },
        },
        controller.signal,
      );
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        const msg = (err as Error).message;
        if (msg.toLowerCase().includes("sign in") || msg.toLowerCase().includes("session expired")) {
          window.localStorage.removeItem(SESSION_KEY);
          setToken("");
          setTenantId("tenant-a");
        }
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  function handleStop() {
    abortRef.current?.abort();
    setBusy(false);
  }

  return (
    <main>
      <h1>Query console</h1>
      {!session && (
        <section className="card" style={{ marginBottom: 16 }}>
          <h2>Login</h2>
          <div className="grid-2">
            <div>
              <label>Username</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div>
              <label>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn" type="button" onClick={handleLogin}>
              Sign in
            </button>
            <span className="badge">demo: analyst / analystpass / tenant-a</span>
          </div>
        </section>
      )}

      <QueryForm
        query={query}
        setQuery={setQuery}
        streaming={streaming}
        debug={debug}
        setStreaming={setStreaming}
        setDebug={setDebug}
        busy={busy}
        onAsk={handleAsk}
        onStop={handleStop}
      />
      {error ? <p style={{ color: "var(--error)" }}>{error}</p> : null}
      <AnswerPanel answer={answer} streaming={busy && streaming} busy={busy} />
      <div className="grid-2" style={{ marginTop: 16, marginBottom: 16 }}>
        <SourcesPanel sources={sources} />
        <RequestInfo requestId={requestId} metadata={metadata} />
      </div>
      {debug ? <DebugPanel metadata={metadata} extra={null} /> : null}
      <div style={{ marginTop: 16 }}>
        <LogPane logs={logs} onClear={() => setLogs([])} />
      </div>
    </main>
  );
}
