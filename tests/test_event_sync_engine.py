"""Tests for the event-driven sync engine and sync-mode service wiring."""

from __future__ import annotations

import json
from queue import Queue

from src.controller.ryu_api_client import RyuAPIClient
from src.twin.config import AppConfig
from src.twin.event_sync_engine import EventSyncEngine
from src.twin.service import TwinService
from src.twin.storage import InMemoryStateStore


def _payload(link_is_up: bool) -> dict[str, object]:
    links = (
        [
            {
                "src": {"dpid": "1", "port_no": 1},
                "dst": {"dpid": "2", "port_no": 1},
            }
        ]
        if link_is_up
        else []
    )
    return {
        "topology_switches": [
            {"dpid": "1", "ports": [{"port_no": 1}]},
            {"dpid": "2", "ports": [{"port_no": 1}]},
        ],
        "links": links,
        "hosts": [],
        "port_descriptions": {
            "0000000000000001": {"1": [{"port_no": 1, "state": 0, "config": 0}]},
            "0000000000000002": {"2": [{"port_no": 1, "state": 0, "config": 0}]},
        },
        "port_stats": {
            "0000000000000001": {"1": [{"port_no": 1, "rx_bytes": 1, "tx_bytes": 2}]},
            "0000000000000002": {"2": [{"port_no": 1, "rx_bytes": 3, "tx_bytes": 4}]},
        },
        "flows": {
            "0000000000000001": {"1": []},
            "0000000000000002": {"2": []},
        },
        "fetch_status": {"topology_switches": True, "links": True},
        "errors": [],
        "api_call_count": 7 if link_is_up else 9,
    }


class SequenceClient(RyuAPIClient):
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self.payloads = list(payloads)
        self.calls = 0
        super().__init__(base_url="http://unused")

    def collect_state_payload(self) -> dict[str, object]:
        self.calls += 1
        index = min(self.calls - 1, len(self.payloads) - 1)
        return self.payloads[index]


def test_event_sync_engine_syncs_after_queue_event() -> None:
    client = SequenceClient([_payload(True), _payload(False)])
    queue: Queue[dict[str, object]] = Queue()
    engine = EventSyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        event_queue=queue,
        event_wait_timeout_seconds=0.0,
    )

    bootstrap = engine.sync_once()
    assert bootstrap.events == []
    assert bootstrap.state.links[0].is_up is True

    queue.put({"event_type": "PORT_STATUS"})
    result = engine.sync_once()

    assert client.calls == 2
    assert [event.event_type for event in result.events] == ["LINK_DOWN"]
    assert result.state.links[0].is_up is False
    assert result.api_call_count == 9


def test_event_sync_engine_hybrid_fallback_detects_missed_change() -> None:
    timeline = iter([0.0, 0.0, 0.0, 0.0, 0.0, 16.0, 16.0, 16.0, 16.0, 16.0])
    client = SequenceClient([_payload(True), _payload(False)])
    engine = EventSyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        event_queue=Queue(),
        event_wait_timeout_seconds=0.0,
        fallback_poll_interval_seconds=10.0,
        monotonic_time=lambda: next(timeline),
    )

    engine.sync_once()
    result = engine.sync_once()

    assert client.calls == 2
    assert [event.event_type for event in result.events] == ["LINK_DOWN"]


def test_event_sync_engine_retries_until_rest_view_reflects_controller_event() -> None:
    client = SequenceClient([_payload(True), _payload(True), _payload(False)])
    queue: Queue[dict[str, object]] = Queue()
    engine = EventSyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        event_queue=queue,
        event_wait_timeout_seconds=0.0,
        event_settle_timeout_seconds=1.0,
        event_settle_poll_seconds=0.0,
    )

    engine.sync_once()
    queue.put({"event_type": "TOPOLOGY_CHANGE"})
    result = engine.sync_once()

    assert client.calls == 3
    assert [event.event_type for event in result.events] == ["LINK_DOWN"]


def test_event_sync_engine_consumes_file_backed_controller_events(tmp_path) -> None:
    client = SequenceClient([_payload(True), _payload(False)])
    stream_path = tmp_path / "controller_events.jsonl"
    engine = EventSyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        event_queue=Queue(),
        event_stream_path=stream_path,
        event_wait_timeout_seconds=0.0,
    )

    engine.sync_once()
    stream_path.write_text(json.dumps({"event_type": "TOPOLOGY_CHANGE"}) + "\n", encoding="utf-8")

    result = engine.sync_once()

    assert client.calls == 2
    assert [event.event_type for event in result.events] == ["LINK_DOWN"]


def test_event_sync_engine_tolerates_partial_json_line_in_event_stream(tmp_path) -> None:
    client = SequenceClient([_payload(True), _payload(False)])
    stream_path = tmp_path / "controller_events.jsonl"
    engine = EventSyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        event_queue=Queue(),
        event_stream_path=stream_path,
        event_wait_timeout_seconds=0.0,
    )

    engine.sync_once()
    stream_path.write_text('{"event_type": "TOPOLOGY_CHANGE"', encoding="utf-8")

    first_retry = engine.sync_once()
    assert client.calls == 1
    assert first_retry.events == []

    stream_path.write_text(json.dumps({"event_type": "TOPOLOGY_CHANGE"}) + "\n", encoding="utf-8")
    second_retry = engine.sync_once()

    assert client.calls == 2
    assert [event.event_type for event in second_retry.events] == ["LINK_DOWN"]


def test_event_sync_engine_resets_offset_after_event_stream_truncation(tmp_path) -> None:
    client = SequenceClient([_payload(True), _payload(False)])
    stream_path = tmp_path / "controller_events.jsonl"
    stream_path.write_text(json.dumps({"event_type": "OLD_EVENT_WITH_LONGER_PAYLOAD"}) + "\n", encoding="utf-8")
    engine = EventSyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        event_queue=Queue(),
        event_stream_path=stream_path,
        event_wait_timeout_seconds=0.0,
    )

    engine.sync_once()
    stream_path.write_text("", encoding="utf-8")
    stream_path.write_text(json.dumps({"event_type": "TOPOLOGY_CHANGE"}) + "\n", encoding="utf-8")
    result = engine.sync_once()

    assert client.calls == 2
    assert [event.event_type for event in result.events] == ["LINK_DOWN"]


def test_twin_service_uses_event_engine_for_non_polling_modes(tmp_path) -> None:
    config = AppConfig(
        sync_mode="event_driven",
        events_log_path=tmp_path / "events.jsonl",
        snapshots_dir=tmp_path / "snapshots",
        exports_dir=tmp_path / "exports",
        plots_dir=tmp_path / "plots",
    )

    service = TwinService(config=config, client=SequenceClient([_payload(True)]))

    assert isinstance(service.sync_engine, EventSyncEngine)


def test_event_sync_engine_reports_zero_api_calls_when_idle() -> None:
    client = SequenceClient([_payload(True)])
    engine = EventSyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        event_queue=Queue(),
        event_wait_timeout_seconds=0.0,
    )

    engine.sync_once()
    result = engine.sync_once()

    assert result.events == []
    assert result.api_call_count == 0
