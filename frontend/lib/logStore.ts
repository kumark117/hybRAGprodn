import type { LogEvent } from "./types";

export const MAX_LOG_ENTRIES = 1000;

export function appendLog(existing: LogEvent[], incoming: LogEvent[]): LogEvent[] {
  const next = existing.concat(incoming);
  if (next.length <= MAX_LOG_ENTRIES) return next;
  return next.slice(next.length - MAX_LOG_ENTRIES);
}

export function filterLogs(
  logs: LogEvent[],
  level: "ALL" | "INFO" | "WARN" | "ERROR",
  stage: string,
): LogEvent[] {
  return logs.filter((item) => {
    if (stage !== "ALL" && item.stage !== stage) return false;
    if (level === "ALL") return true;
    if (level === "ERROR") return item.level === "ERROR";
    if (level === "WARN") return item.level === "WARN" || item.level === "ERROR";
    return true;
  });
}

export function fromSseLog(payload: Record<string, unknown>): LogEvent {
  return {
    requestId: String(payload.request_id ?? payload.requestId ?? ""),
    timestamp: String(payload.timestamp ?? new Date().toISOString()),
    level: (payload.level as LogEvent["level"]) ?? "INFO",
    stage: String(payload.stage ?? "REQUEST"),
    event: String(payload.event ?? ""),
    message: String(payload.message ?? ""),
    durationMs:
      typeof payload.duration_ms === "number"
        ? payload.duration_ms
        : typeof payload.durationMs === "number"
          ? payload.durationMs
          : undefined,
    metadata:
      payload.metadata && typeof payload.metadata === "object"
        ? (payload.metadata as Record<string, unknown>)
        : undefined,
  };
}
