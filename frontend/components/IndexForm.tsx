"use client";

import { useRef } from "react";

export function IndexForm({
  documentId,
  setDocumentId,
  text,
  setText,
  source,
  setSource,
  busy,
  folderStatus,
  folderStatusKind,
  onSubmit,
  onFolder,
}: {
  documentId: string;
  setDocumentId: (value: string) => void;
  text: string;
  setText: (value: string) => void;
  source: string;
  setSource: (value: string) => void;
  busy: boolean;
  folderStatus: string;
  folderStatusKind: "idle" | "busy" | "ok" | "err";
  onSubmit: () => void;
  onFolder: (files: FileList) => void;
}) {
  const folderInput = useRef<HTMLInputElement>(null);

  return (
    <section className="card">
      <h2>Index a folder</h2>
      <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 0 }}>
        Pick a directory here, or from a terminal:{" "}
        <code>python -m app.cli index-folder docs</code>
      </p>
      <input
        ref={folderInput}
        className="file-hidden"
        type="file"
        multiple
        disabled={busy}
        aria-label="Choose folder to index"
        onChange={(e) => {
          if (e.target.files && e.target.files.length) onFolder(e.target.files);
          e.target.value = "";
        }}
        {...{ webkitdirectory: "", directory: "" }}
      />
      <div className="row">
        <button
          className="btn"
          type="button"
          disabled={busy}
          onClick={() => folderInput.current?.click()}
        >
          {busy ? "Indexing folder…" : "Choose folder"}
        </button>
        <span className="badge">.md .txt .py and other text files</span>
      </div>
      {folderStatus ? (
        <div className={`status-banner ${folderStatusKind === "idle" ? "" : folderStatusKind}`}>
          {folderStatus}
        </div>
      ) : null}

      <h2 style={{ marginTop: 28 }}>Or paste one document</h2>
      <label>Document ID</label>
      <input value={documentId} onChange={(e) => setDocumentId(e.target.value)} />
      <label style={{ marginTop: 10 }}>Source filename</label>
      <input value={source} onChange={(e) => setSource(e.target.value)} />
      <label style={{ marginTop: 10 }}>Text</label>
      <textarea value={text} onChange={(e) => setText(e.target.value)} style={{ minHeight: 180 }} />
      <div className="row" style={{ marginTop: 12 }}>
        <button className="btn" type="button" disabled={busy || !text.trim()} onClick={onSubmit}>
          Index with live logs
        </button>
      </div>
    </section>
  );
}
