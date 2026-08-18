# High-cardinality Prometheus labels

## Outage shape

Prometheus RAM climbed for 6 hours then OOM. Grafana timed out. The RAG service was fine. Observability was not.

## Cause

Someone added `request_id` and `user_id` as metric labels “for debugging.” Each request created new time series. Cardinality exploded.

## Rule

Metrics answer **how is the service behaving?**
Logs/traces answer **what happened on request req-abc?**

Safe labels: `retrieval_mode`, `cache`, `provider`, `result`, `stage`.

Unsafe labels: `request_id`, `user_id`, `query_text`, raw `document_id` at high volume.

Put correlation IDs on structured logs and OpenTelemetry spans, not on `/metrics`.

See also `docs/observability.md`.
