import { parseSseBlock, parseSseChunk } from "./sse";
import { describe, expect, it } from "vitest";

describe("SSE parser", () => {
  it("parses a log frame", () => {
    const frame = parseSseBlock(
      'event: log\ndata: {"request_id":"req-1","message":"hi"}',
    );
    expect(frame?.event).toBe("log");
    expect(JSON.parse(frame!.data).request_id).toBe("req-1");
  });

  it("ignores heartbeat comments", () => {
    const { frames, rest } = parseSseChunk("", ": heartbeat\n\nevent: token\ndata: {\"text\":\"Hi\"}\n\n");
    expect(frames).toHaveLength(1);
    expect(frames[0].event).toBe("token");
    expect(rest).toBe("");
  });

  it("keeps incomplete frames in the buffer", () => {
    const { frames, rest } = parseSseChunk("", "event: log\ndata: {\"a\":");
    expect(frames).toHaveLength(0);
    expect(rest.startsWith("event:")).toBe(true);
  });
});
