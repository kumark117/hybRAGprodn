import type {
  IndexRequest,
  IndexResult,
  QueryRequest,
  SSEHandler,
  TokenResponse,
} from "./types";
import { fromSseLog } from "./logStore";
import { readSseStream } from "./sse";
import type { RAGMetadata } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function apiBase(): string {
  return API_BASE.replace(/\/$/, "");
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  const response = await fetch(`${apiBase()}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error("Login failed");
  }
  return (await response.json()) as TokenResponse;
}

function authHeaders(token: string, extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("Content-Type", "application/json");
  return headers;
}

export async function indexDocument(
  token: string,
  body: IndexRequest,
  signal?: AbortSignal,
): Promise<IndexResult> {
  const response = await fetch(`${apiBase()}/api/v1/index`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    let detail = `Index failed (${response.status})`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      if (body.error?.message) detail = body.error.message;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return (await response.json()) as IndexResult;
}

export async function streamQuery(
  token: string,
  body: QueryRequest,
  handlers: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${apiBase()}/api/v1/query/stream`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    let detail = `Query stream failed (${response.status})`;
    try {
      const payload = (await response.json()) as { error?: { message?: string } };
      if (payload.error?.message) detail = payload.error.message;
    } catch {
      /* keep status text */
    }
    if (response.status === 401) detail = `Session expired. Please sign in again. (${detail})`;
    throw new Error(detail);
  }
  await dispatchSse(response, handlers, signal);
}

export async function streamIndex(
  token: string,
  body: IndexRequest,
  handlers: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${apiBase()}/api/v1/index/stream`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    throw new Error(`Index stream failed (${response.status})`);
  }
  await dispatchSse(response, handlers, signal);
}

async function dispatchSse(
  response: Response,
  handlers: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  await readSseStream(
    response,
    (frame) => {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(frame.data) as Record<string, unknown>;
      } catch {
        return;
      }
      const requestId = String(payload.request_id ?? "");
      switch (frame.event) {
        case "log":
          handlers.onLog?.(fromSseLog(payload));
          break;
        case "token":
          handlers.onToken?.({ requestId, text: String(payload.text ?? "") });
          break;
        case "citation":
          handlers.onCitation?.({ requestId, ...payload });
          break;
        case "metadata":
          handlers.onMetadata?.((payload.metadata ?? payload) as RAGMetadata);
          break;
        case "error":
          handlers.onError?.({
            requestId,
            code: String(payload.code ?? "ERROR"),
            message: String(payload.message ?? "Request failed"),
          });
          break;
        case "done":
          handlers.onDone?.({
            requestId,
            latencyMs: Number(payload.latency_ms ?? 0),
            retrievalMode: String(payload.retrieval_mode ?? ""),
            cacheHit: Boolean(payload.cache_hit),
            answer: payload.answer != null ? String(payload.answer) : undefined,
          });
          break;
        default:
          break;
      }
    },
    signal,
  );
}
