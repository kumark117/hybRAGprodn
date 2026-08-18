import pytest

from app.observability.event_bus import CompositeEventSink, NullEventSink
from app.observability.events import ObservabilityEvent


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    async def emit(self, event: ObservabilityEvent) -> None:
        self.events.append(event)


class ExplodingSink:
    async def emit(self, event: ObservabilityEvent) -> None:
        raise RuntimeError("sink down")


@pytest.mark.asyncio
async def test_composite_fanout_survives_sink_failure() -> None:
    good = RecordingSink()
    bus = CompositeEventSink([ExplodingSink(), good, NullEventSink()])
    event = ObservabilityEvent(request_id="req-abcdef12", event="x", message="y")
    await bus.emit(event)
    assert len(good.events) == 1
