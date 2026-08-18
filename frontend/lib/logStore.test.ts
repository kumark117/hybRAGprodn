import { describe, expect, it } from "vitest";
import { MAX_LOG_ENTRIES, appendLog, filterLogs } from "./logStore";
import type { LogEvent } from "./types";

function log(i: number, level: LogEvent["level"] = "INFO"): LogEvent {
  return {
    requestId: "req-1",
    timestamp: new Date().toISOString(),
    level,
    stage: "CACHE",
    event: "e",
    message: String(i),
  };
}

describe("log store", () => {
  it("drops oldest entries beyond the bound", () => {
    const seed = Array.from({ length: MAX_LOG_ENTRIES }, (_, i) => log(i));
    const next = appendLog(seed, [log(MAX_LOG_ENTRIES)]);
    expect(next).toHaveLength(MAX_LOG_ENTRIES);
    expect(next[0].message).toBe("1");
    expect(next[next.length - 1].message).toBe(String(MAX_LOG_ENTRIES));
  });

  it("filters by level", () => {
    const logs = [log(1, "INFO"), log(2, "WARN"), log(3, "ERROR")];
    expect(filterLogs(logs, "ERROR", "ALL")).toHaveLength(1);
    expect(filterLogs(logs, "WARN", "ALL")).toHaveLength(2);
  });
});
