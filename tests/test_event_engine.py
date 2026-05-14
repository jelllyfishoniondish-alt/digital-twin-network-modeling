"""Tests for mapping state changes into event records."""

from src.twin.diff_engine import StateChange
from src.twin.event_engine import build_events, build_sync_error_events


def test_build_events_generates_link_events() -> None:
    changes = [
        StateChange(
            entity_type="link",
            entity_id="0000000000000001:2--0000000000000002:1",
            field_name="is_up",
            old_value=True,
            new_value=False,
            details={"src_dpid": "0000000000000001", "dst_dpid": "0000000000000002"},
        )
    ]

    events = build_events(changes, "2026-04-01T12:00:02+00:00")

    assert len(events) == 1
    assert events[0].event_type == "LINK_DOWN"
    assert events[0].entity_id == "0000000000000001:2--0000000000000002:1"


def test_build_sync_error_events_generates_sync_error() -> None:
    events = build_sync_error_events(
        [{"endpoint": "/stats/switches", "message": "timeout"}],
        "2026-04-01T12:00:04+00:00",
    )

    assert len(events) == 1
    assert events[0].event_type == "SYNC_ERROR"
    assert events[0].entity_id == "/stats/switches"


def test_build_events_generates_switch_and_host_events() -> None:
    changes = [
        StateChange(
            entity_type="switch",
            entity_id="0000000000000001",
            field_name="presence",
            old_value=True,
            new_value=False,
            details={"name": "s1"},
        ),
        StateChange(
            entity_type="host",
            entity_id="00:00:00:00:00:01",
            field_name="presence",
            old_value=False,
            new_value=True,
            details={"name": "h1"},
        ),
        StateChange(
            entity_type="host",
            entity_id="00:00:00:00:00:02",
            field_name="attached_switch",
            old_value="1",
            new_value="2",
            details={"name": "h2"},
        ),
    ]

    events = build_events(changes, "2026-04-01T12:00:02+00:00")

    assert [event.event_type for event in events] == ["SWITCH_DOWN", "HOST_JOIN", "HOST_MIGRATE"]
