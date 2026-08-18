# On-call checklist for this RAG service

1. `/health/live` 200? If not, the process is dead — restart, don’t tune Pinecone.
2. `/health/ready` — which check is degraded?
3. `/metrics` — `rag_errors_total`, `rag_degraded_requests_total`, `rag_failovers_total`, TTFT histogram
4. Logs: grep one `request_id` from a failing user (they can copy it from the UI)
5. Is `degraded_mode` true? Then retrieve path is already telling you BM25-only or vector-only
6. Is `fallback_used` true? Quality may have dropped (INC-4012)
7. Redis optional? Fail-open means cache is a red herring
8. Recent deploy change embedding model? Dimension mismatch
9. Multiple API replicas + fake BM25? INC-2044
10. Do not paste JWTs into Slack; request_id is enough

The Log Pane is a flashlight, not the archive. Ship JSON logs to Loki/ELK/Datadog in production.
