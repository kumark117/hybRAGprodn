/**
 * Visible SSE parser.
 *
 * Native EventSource only supports GET. RAG streaming is POST, so we read
 * the fetch() ReadableStream and assemble frames ourselves.
 *
 * A frame looks like:
 *
 *   event: log
 *   data: {"request_id":"..."}
 *
 *   (blank line)
 *
 * Heartbeat comments (`: heartbeat`) are ignored.
 */

export interface SSEFrame {
  event: string;
  data: string;
}

export function parseSseChunk(
  buffer: string,
  chunk: string,
): { frames: SSEFrame[]; rest: string } {
  const combined = buffer + chunk;
  const frames: SSEFrame[] = [];
  const parts = combined.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    const frame = parseSseBlock(block);
    if (frame) frames.push(frame);
  }
  return { frames, rest };
}

export function parseSseBlock(block: string): SSEFrame | null {
  const lines = block.replace(/\r/g, "").split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}

export async function readSseStream(
  response: Response,
  onFrame: (frame: SSEFrame) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) {
    throw new Error("Response has no body to stream");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        break;
      }
      const { value, done } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      const parsed = parseSseChunk(buffer, text);
      buffer = parsed.rest;
      for (const frame of parsed.frames) {
        onFrame(frame);
      }
    }
    if (buffer.trim()) {
      const frame = parseSseBlock(buffer);
      if (frame) onFrame(frame);
    }
  } finally {
    reader.releaseLock();
  }
}
