"""Tests for controller event queue publishing."""

from __future__ import annotations

import json

from src.controller import event_queue


def test_publish_controller_event_writes_queue_depth(monkeypatch, tmp_path) -> None:
    stream_path = tmp_path / "controller_events.jsonl"
    monkeypatch.setenv("EVENT_STREAM_PATH", str(stream_path))
    event_queue._CONTROLLER_EVENT_QUEUE = event_queue.Queue()  # type: ignore[attr-defined]

    event_queue.publish_controller_event("PORT_STATUS", port_no=3)

    payload = json.loads(stream_path.read_text(encoding="utf-8").strip())
    assert payload["event_type"] == "PORT_STATUS"
    assert payload["queue_depth_after_put"] == 1
