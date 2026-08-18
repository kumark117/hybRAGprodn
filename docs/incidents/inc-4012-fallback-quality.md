# Failover succeeded, answer quality dropped (INC-4012)

## Report

`fallback_used=true`. Latency recovered. Legal reviewed an answer that missed a citation the primary model always included. The fallback was a smaller, cheaper model.

## Lesson

Failover is an **availability** tool, not a free quality upgrade. Record `llm_model` in request metadata and dashboards. Alert on fallback rate, not only on 5xx.

If fallback quality is unacceptable for a tenant (healthcare, finance), fail the request after primary exhaustion instead of silently switching. That is a product decision.

This app always tries fallback after retry budget. For regulated workloads, gate that with a flag.

## What to show in the UI

Request info already includes model name, `fallback_used`, and `degraded_mode`. Teach operators to read those before trusting a surprising answer.
