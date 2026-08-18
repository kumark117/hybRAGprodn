# Retry policy — timeouts, backoff, jitter

Incident reference: INC-1044 (2025-11-02)

## Symptom

p99 query latency jumped from 1.8s to 28s. LLM provider dashboards showed a 12-minute brownout. Our pods did not crash. Users saw spinning “Generation started” with no first token.

## What went wrong

`LLM_TIMEOUT_SECONDS` was unset, so HTTP clients waited on the default socket timeout (effectively “forever” for the user). When the vendor recovered, every in-flight request plus every user retry hit the API at once.

## Rules

TIMEOUT is how long **one attempt** may wait.

RETRY is whether **another attempt** is allowed after a transient error.

Never retry:

- HTTP 400 validation
- HTTP 401 / 403
- Pydantic schema failures
- “document too large”

Always consider retrying:

- 429 Too Many Requests
- 408 / timeouts
- 502, 503, 504
- connection resets

## Backoff

Use exponential backoff **with jitter**:

```
delay = random(0, min(max_wait, base * 2^(attempt-1)))
```

Without jitter, thousands of pods retry on the same 1s / 2s / 4s cadence. That is a thundering herd. Jitter spreads the retries.

## Config in this app

`MAX_RETRIES`, `RETRY_BASE_SECONDS`, `RETRY_MAX_SECONDS`, `LLM_TIMEOUT_SECONDS`.

Watch the Live Log Pane for:

```
WARN  LLM      Timeout attempt=1
INFO  RETRY    retrying in 0.62 sec
ERROR LLM      Retry budget exhausted
WARN  FAILOVER switching to fallback provider
```
