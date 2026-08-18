# SSE dropped behind nginx (INC-3180)

## Symptom

curl -N showed tokens. Chrome Log Pane froze after 60s. Heartbeats were missing. Nginx `proxy_read_timeout` defaulted to 60s. The connection was idle during a slow first token.

## Fixes

- Send SSE comments on an interval (`: heartbeat`) — this app uses `SSE_HEARTBEAT_SECONDS`
- `X-Accel-Buffering: no` so nginx does not buffer the stream
- `proxy_read_timeout` well above worst-case LLM time (e.g. 120s+)
- `Cache-Control: no-cache`

## SSE vs WebSocket

RAG is almost entirely **server → browser** (logs + tokens). SSE over HTTP is enough. WebSocket is for bidirectional chatter.

EventSource GET cannot send Authorization bodies easily; this app uses **POST + fetch ReadableStream**.

## Backpressure

`SSE_QUEUE_MAX_SIZE` bounds memory. A stuck laptop must not grow an unbounded asyncio queue. Low-priority INFO may drop; ERROR/DONE try to survive.
