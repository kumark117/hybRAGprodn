# Circuit breakers vs retries

Incident reference: INC-1188 (retry storm against Pinecone)

## The failure

Pinecone regional blip, ~90 seconds. Each query retried 3 times with backoff. 200 FastAPI replicas × 40 QPS × 3 attempts ≈ a self-inflicted DDoS. After Pinecone recovered, our error rate stayed high because we kept amplifying load.

## Distinction

Retry asks: “try **this call** again?”

Circuit breaker asks: “should we call this **dependency at all** right now?”

States:

- CLOSED — normal traffic
- OPEN — fail fast; do not call the dependency
- HALF_OPEN — allow one trial; success closes, failure re-opens

If the circuit is OPEN, further retries are harmful. Fail fast and degrade (BM25-only).

## What to log

```
ERROR VECTOR   circuit_opened failures=5
WARN  VECTOR   circuit_call_rejected
INFO  MODE     degraded_mode=true retrieval_mode=bm25_only
INFO  VECTOR   circuit_half_open
INFO  VECTOR   circuit_closed
```

## Tuning

`CIRCUIT_FAILURE_THRESHOLD` (default 5) and `CIRCUIT_RESET_SECONDS` (default 30).

Too sensitive: breaker flaps on one slow query.
Too insensitive: you retry-storm anyway.

A breaker is not a substitute for timeouts. Timeouts still bound each attempt.
