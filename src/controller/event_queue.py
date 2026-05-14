"""Shared controller-to-twin event queue used by event-driven sync mode."""

from __future__ import annotations

import json
import os
from pathlib import Path
from queue import Queue
from typing import Any

from src.twin.models import utc_now_iso


_CONTROLLER_EVENT_QUEUE: Queue[dict[str, Any]] = Queue()


def get_controller_event_queue() -> Queue[dict[str, Any]]:
    """Return the process-local queue used for controller event notifications."""

    return _CONTROLLER_EVENT_QUEUE


def publish_controller_event(event_type: str, **details: Any) -> None:
    """Publish a lightweight controller event for the event-driven twin engine."""

    _CONTROLLER_EVENT_QUEUE.put(
        {
            "timestamp": utc_now_iso(),
            "event_type": event_type,
            "details": details,
        }
    )
    queue_depth_after_put = _CONTROLLER_EVENT_QUEUE.qsize()
    payload = {
        "timestamp": utc_now_iso(),
        "event_type": event_type,
        "details": details,
        # This is a controller-side backlog proxy emitted from the Ryu process.
        "queue_depth_after_put": queue_depth_after_put,
    }

    stream_path = Path(
        os.getenv(
            "EVENT_STREAM_PATH",
            str(Path(__file__).resolve().parents[2] / "data" / "events" / "controller_events.jsonl"),
        )
    )
    stream_path.parent.mkdir(parents=True, exist_ok=True)
    with stream_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")
