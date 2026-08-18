"use client";

import { useRef, useState } from "react";
import { indexDocument, login, streamIndex } from "@/lib/api";
import { appendLog } from "@/lib/logStore";
import type { LogEvent } from "@/lib/types";
import { IndexForm } from "@/components/IndexForm";
import { LogPane } from "@/components/LogPane";

const SESSION_KEY = "rag.token";
const TEXT_EXT = new Set([
  ".md",
  ".txt",
  ".rst",
  ".py",
  ".json",
  ".yml",
  ".yaml",
  ".toml",
  ".csv",
  ".log",
  ".html",
  ".htm",
  ".xml",
  ".ts",
  ".tsx",
  ".js",
  ".jsx",
  ".go",
  ".rs",
  ".java",
  ".sql",
]);

const SAMPLE = `Retries apply only to transient failures such as HTTP 429, 502, 503, 504, timeouts, and connection errors. Permanent errors including 400, 401, and 403 are never retried. Each attempt has an explicit timeout. Backoff is exponential with random jitter. After the retry budget is exhausted the system may fail over to a fallback model. Circuit breakers open after consecutive failures so retry storms cannot take down a dependency.`;

function documentIdFor(relative: string): string {
  const slug = relative.replace(/\\/g, "/").replace(/\//g, "__");
  return slug.length > 0 && slug.length <= 120 ? slug : `doc_${slug.slice(0, 24)}`;
}

function extension(name: string): string {
  const idx = name.lastIndexOf(".");
  return idx >= 0 ? name.slice(idx).toLowerCase() : "";
}

export default function IndexingPage() {
  const [documentId, setDocumentId] = useState("retry-guide");
  const [source, setSource] = useState("retry-guide.md");
  const [text, setText] = useState(SAMPLE);
  const [busy, setBusy] = useState(false);
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [status, setStatus] = useState("");
  const [folderStatus, setFolderStatus] = useState("");
  const [folderStatusKind, setFolderStatusKind] = useState<"idle" | "busy" | "ok" | "err">("idle");
  const abortRef = useRef<AbortController | null>(null);

  async function handleSubmit() {
    const token = window.localStorage.getItem(SESSION_KEY);
    if (!token) {
      setStatus("Login on the Query page first.");
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setLogs([]);
    setStatus("Indexing…");
    try {
      await streamIndex(
        token,
        {
          document_id: documentId,
          tenant_id: "tenant-a",
          text,
          metadata: { source },
        },
        {
          onLog: (event) => setLogs((prev) => appendLog(prev, [event])),
          onError: (event) => setStatus(event.message),
          onDone: () => setStatus("Index complete"),
          onMetadata: () => setStatus("Index complete"),
        },
        controller.signal,
      );
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleFolder(fileList: FileList) {
    const token = window.localStorage.getItem(SESSION_KEY);
    if (!token) {
      setFolderStatusKind("err");
      setFolderStatus("Login on the Query page first.");
      return;
    }
    const files = Array.from(fileList).filter((file) => TEXT_EXT.has(extension(file.name)));
    const folderName =
      files[0]?.webkitRelativePath.split(/[/\\]/)[0] ||
      fileList[0]?.webkitRelativePath.split(/[/\\]/)[0] ||
      "folder";
    if (!files.length) {
      setFolderStatusKind("err");
      setFolderStatus(`No indexable text files in ${folderName}.`);
      setStatus("");
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    setLogs([]);
    setFolderStatusKind("busy");
    setFolderStatus(`Indexing ${files.length} files from ${folderName}…`);
    setStatus("");
    let ok = 0;
    try {
      for (const file of files) {
        const relative = file.webkitRelativePath || file.name;
        const contents = (await file.text()).trim();
        if (!contents) continue;
        const result = await indexDocument(
          token,
          {
            document_id: documentIdFor(relative),
            tenant_id: "tenant-a",
            text: contents,
            metadata: { source: relative },
          },
          controller.signal,
        );
        ok += 1;
        setLogs((prev) =>
          appendLog(prev, [
            {
              requestId: result.request_id,
              timestamp: new Date().toISOString(),
              level: "OK",
              stage: "INDEX",
              event: "index_complete",
              message: `${relative}  chunks=${result.chunks_created}  vectors=${result.vectors_indexed}`,
            },
          ]),
        );
        setFolderStatus(`Indexed ${ok}/${files.length}: ${relative}`);
      }
      setFolderStatusKind("ok");
      setFolderStatus(
        `Done. Indexed ${ok} file${ok === 1 ? "" : "s"} from ${folderName}. Open Query and ask something like “What is E-2044?”`,
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      const message = (err as Error).message || "Indexing failed";
      setFolderStatusKind("err");
      setFolderStatus(
        message === "Failed to fetch"
          ? "Could not reach the API. Is uvicorn running on http://localhost:8000?"
          : message,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Indexing</h1>
      <IndexForm
        documentId={documentId}
        setDocumentId={setDocumentId}
        text={text}
        setText={setText}
        source={source}
        setSource={setSource}
        busy={busy}
        onSubmit={handleSubmit}
        onFolder={handleFolder}
        folderStatus={folderStatus}
        folderStatusKind={folderStatusKind}
      />
      {status ? <p>{status}</p> : null}
      <div style={{ marginTop: 16 }}>
        <LogPane logs={logs} onClear={() => setLogs([])} />
      </div>
    </main>
  );
}
