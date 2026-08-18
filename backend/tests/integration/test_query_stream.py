import json

import pytest

from tests.integration.conftest import RETRY_DOC


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event_name = "message"
    data_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "":
            if data_lines:
                payload = json.loads("\n".join(data_lines))
                events.append((event_name, payload))
            event_name = "message"
            data_lines = []
    if data_lines:
        events.append((event_name, json.loads("\n".join(data_lines))))
    return events


@pytest.mark.asyncio
async def test_query_stream_emits_log_token_citation_done(client, auth_header) -> None:
    await client.post("/api/v1/index", json=RETRY_DOC, headers=auth_header)
    response = await client.post(
        "/api/v1/query/stream",
        json={
            "query": "How does the system handle retries?",
            "tenant_id": "tenant-a",
            "use_cache": False,
        },
        headers=auth_header,
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    names = [name for name, _ in events]
    assert "log" in names
    assert "token" in names
    assert "done" in names
    assert names.index("log") < names.index("done")
    stages = {payload.get("stage") for name, payload in events if name == "log"}
    assert "REQUEST" in stages
    assert "CACHE" in stages
    assert "LLM" in stages or "BM25" in stages
