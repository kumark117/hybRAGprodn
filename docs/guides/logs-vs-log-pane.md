# Structured logs are not the Log Pane

The browser pane is request-scoped, capped at 1000 lines, gone when you close the tab.

Production needs:

- JSON logs with `request_id`, `stage`, `duration_ms`, `tenant_id`
- Redaction of Bearer tokens, API keys, Redis URLs
- A sink: Loki, OpenSearch, Datadog, CloudWatch, GCP Logging

If an incident lasts 4 hours, nobody will scroll a pane. They will grep `INC-2044` or `E-2044` in the log backend.

`StructuredLogSink` already emits JSON. Wire stdout to your collector; do not invent a second logging API.
