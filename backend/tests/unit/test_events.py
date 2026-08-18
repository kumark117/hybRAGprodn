import json

from app.observability.events import ObservabilityEvent
from app.observability.sse_sink import encode_heartbeat, encode_sse


def test_event_serialization_contains_correlation_fields() -> None:
    event = ObservabilityEvent(
        request_id="req-12345678",
        stage="RERANK",
        event="rerank_completed",
        message="Selected 6 chunks",
        duration_ms=87,
        tenant_id="tenant-a",
        metadata={"input_candidates": 27, "output_candidates": 6},
    )
    payload = event.to_log_dict()
    assert payload["request_id"] == "req-12345678"
    assert payload["stage"] == "RERANK"
    sse = encode_sse("log", event.to_sse_payload())
    assert sse.startswith("event: log\n")
    assert sse.endswith("\n\n")
    data_line = sse.split("\n")[1]
    parsed = json.loads(data_line.removeprefix("data: "))
    assert parsed["event"] == "rerank_completed"


def test_heartbeat_is_sse_comment() -> None:
    assert encode_heartbeat().startswith(": ")
