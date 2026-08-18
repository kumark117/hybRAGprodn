"use client";

import { useEffect, useRef, useState } from "react";
import type { LogEvent, LogLevel } from "@/lib/types";
import { filterLogs } from "@/lib/logStore";

const STAGES = [
  "ALL",
  "REQUEST",
  "AUTH",
  "CACHE",
  "REWRITE",
  "EMBED",
  "VECTOR",
  "BM25",
  "RRF",
  "DEDUP",
  "RERANK",
  "CONTEXT",
  "PROMPT",
  "LLM",
  "RETRY",
  "FAILOVER",
  "INDEX",
  "COMPLETE",
];

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().slice(11, 23);
}

export function LogPane({
  logs,
  onClear,
}: {
  logs: LogEvent[];
  onClear: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const [level, setLevel] = useState<"ALL" | "INFO" | "WARN" | "ERROR">("ALL");
  const [stage, setStage] = useState("ALL");
  const [expanded, setExpanded] = useState<number | null>(null);
  const visible = filterLogs(logs, level, stage);

  useEffect(() => {
    if (paused) return;
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [visible, paused]);

  return (
    <section className="card">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 10 }}>
        <h2 style={{ margin: 0 }}>Live RAG log</h2>
        <div className="row">
          <span className="badge">{logs.length} events</span>
          <button className="btn secondary" type="button" onClick={() => setPaused((p) => !p)}>
            {paused ? "Resume scroll" : "Pause scroll"}
          </button>
          <button className="btn secondary" type="button" onClick={onClear}>
            Clear
          </button>
        </div>
      </div>
      <div className="filters">
        {(["ALL", "INFO", "WARN", "ERROR"] as const).map((item) => (
          <button
            key={item}
            className="btn secondary"
            type="button"
            onClick={() => setLevel(item)}
            style={{ borderColor: level === item ? "var(--accent)" : undefined }}
          >
            {item}
          </button>
        ))}
        <select value={stage} onChange={(e) => setStage(e.target.value)} style={{ maxWidth: 180 }}>
          {STAGES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <div className="log-pane" ref={scroller}>
        {visible.length === 0 ? (
          <div style={{ color: "var(--muted)" }}>Waiting for pipeline events…</div>
        ) : (
          visible.map((item, index) => (
            <div key={`${item.timestamp}-${index}`}>
              <div className="log-row" onClick={() => setExpanded(expanded === index ? null : index)}>
                <span style={{ color: "var(--muted)" }}>{formatTime(item.timestamp)}</span>
                <span className={`lvl-${item.level}`}>{item.level.padEnd(5, " ")}</span>
                <span style={{ color: "var(--accent-2)" }}>{item.stage}</span>
                <span>
                  {item.message}
                  {item.durationMs != null ? `  (${Math.round(item.durationMs)} ms)` : ""}
                </span>
              </div>
              {expanded === index && item.metadata && (
                <pre className="log-meta">{JSON.stringify(item.metadata, null, 2)}</pre>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export type { LogLevel };
