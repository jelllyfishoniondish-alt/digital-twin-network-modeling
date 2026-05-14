"""Event-driven sync engine backed by controller notifications and optional polling fallback."""

from __future__ import annotations

import json
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable

from src.controller.event_queue import get_controller_event_queue
from src.controller.ryu_api_client import RyuAPIClient
from src.topology.topology_loader import TopologyDefinition
from src.twin.event_engine import build_events, build_sync_error_events
from src.twin.models import utc_now_iso
from src.twin.storage import InMemoryStateStore, JsonLineEventStore, JsonSnapshotStore
from src.twin.sync_engine import SyncResult, build_network_state
from src.twin.diff_engine import StateChange, diff_network_states


class EventSyncEngine:
    """Event-driven synchronizer that reacts to controller-side notifications."""

    def __init__(
        self,
        client: RyuAPIClient,
        state_store: InMemoryStateStore,
        snapshot_store: JsonSnapshotStore | None = None,
        event_store: JsonLineEventStore | None = None,
        topology_definition: TopologyDefinition | None = None,
        event_queue: Queue[dict[str, Any]] | None = None,
        event_stream_path: Path | None = None,
        event_wait_timeout_seconds: float = 0.5,
        fallback_poll_interval_seconds: float | None = None,
        event_settle_timeout_seconds: float = 1.0,
        event_settle_poll_seconds: float = 0.1,
        monotonic_time: Callable[[], float] | None = None,
    ) -> None:
        self.client = client
        self.state_store = state_store
        self.snapshot_store = snapshot_store
        self.event_store = event_store
        self.switch_metadata_by_dpid = topology_definition.switches_by_dpid() if topology_definition else {}
        self.link_metadata_by_dpid_pair = (
            topology_definition.link_metadata_by_dpid_pair() if topology_definition else {}
        )
        self.event_queue = event_queue or get_controller_event_queue()
        self.event_stream_path = event_stream_path
        self.event_wait_timeout_seconds = event_wait_timeout_seconds
        self.fallback_poll_interval_seconds = fallback_poll_interval_seconds
        self.event_settle_timeout_seconds = event_settle_timeout_seconds
        self.event_settle_poll_seconds = event_settle_poll_seconds
        self._monotonic_time = monotonic_time or time.monotonic
        self._last_full_sync_at: float | None = None
        self._event_stream_offset = 0
        if self.event_stream_path is not None and self.event_stream_path.exists():
            self._event_stream_offset = self.event_stream_path.stat().st_size

    def _drain_queue(self, timeout_seconds: float) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        try:
            if timeout_seconds > 0:
                events.append(self.event_queue.get(timeout=timeout_seconds))
            else:
                events.append(self.event_queue.get_nowait())
        except Empty:
            return events

        while True:
            try:
                events.append(self.event_queue.get_nowait())
            except Empty:
                return events

    def _drain_event_stream(self) -> list[dict[str, Any]]:
        if self.event_stream_path is None or not self.event_stream_path.exists():
            return []
        current_size = self.event_stream_path.stat().st_size
        if current_size < self._event_stream_offset:
            self._event_stream_offset = 0

        events: list[dict[str, Any]] = []
        with self.event_stream_path.open("r", encoding="utf-8") as handle:
            handle.seek(self._event_stream_offset)
            while True:
                line_start = handle.tell()
                line = handle.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    self._event_stream_offset = line_start
                    return events
            self._event_stream_offset = handle.tell()
        return events

    def _process_payload(self, payload: dict[str, Any], previous_state) -> SyncResult:
        started_at = self._monotonic_time()
        timestamp = utc_now_iso()
        fetch_status = payload.get("fetch_status", {})
        topology_switches_ok = fetch_status.get("topology_switches", True)
        topology_links_ok = fetch_status.get("links", True)
        observation_missing = (
            not payload.get("topology_switches")
            and not payload.get("links")
            and not topology_switches_ok
            and not topology_links_ok
        )

        if previous_state is not None and observation_missing:
            state = previous_state
            changes: list[StateChange] = []
        else:
            state = build_network_state(
                payload,
                timestamp=timestamp,
                previous_state=previous_state,
                preserve_previous_links=previous_state is not None and not topology_links_ok,
                switch_metadata_by_dpid=self.switch_metadata_by_dpid,
                link_metadata_by_dpid_pair=self.link_metadata_by_dpid_pair,
            )
            changes = diff_network_states(previous_state, state)

        events = build_events(changes, timestamp)
        events.extend(build_sync_error_events(payload.get("errors", []), timestamp))

        self.state_store.set_current_state(state)
        if self.snapshot_store is not None:
            self.snapshot_store.save(state)
        if self.event_store is not None:
            self.event_store.append_many(events)

        self._last_full_sync_at = self._monotonic_time()
        return SyncResult(
            state=state,
            changes=changes,
            events=events,
            errors=payload.get("errors", []),
            sync_duration_ms=(self._monotonic_time() - started_at) * 1000,
            api_call_count=payload.get("api_call_count"),
        )

    def sync_once(self) -> SyncResult:
        previous_state = self.state_store.get_current_state()
        started_at = self._monotonic_time()
        now = self._monotonic_time()

        if previous_state is None:
            return self._process_payload(self.client.collect_state_payload(), previous_state)

        fallback_due = (
            self.fallback_poll_interval_seconds is not None
            and (
                self._last_full_sync_at is None
                or now - self._last_full_sync_at >= self.fallback_poll_interval_seconds
            )
        )
        queue_timeout = 0.0 if fallback_due else self.event_wait_timeout_seconds
        queue_events = self._drain_queue(queue_timeout)
        stream_events = self._drain_event_stream()

        controller_events_seen = bool(queue_events or stream_events)

        if not controller_events_seen and not fallback_due:
            return SyncResult(
                state=previous_state,
                changes=[],
                events=[],
                errors=[],
                sync_duration_ms=(self._monotonic_time() - started_at) * 1000,
                api_call_count=0,
            )

        if controller_events_seen:
            settle_deadline = self._monotonic_time() + self.event_settle_timeout_seconds
            last_result = self._process_payload(self.client.collect_state_payload(), previous_state)
            while (
                not last_result.changes
                and not last_result.errors
                and self._monotonic_time() < settle_deadline
            ):
                time.sleep(self.event_settle_poll_seconds)
                last_result = self._process_payload(self.client.collect_state_payload(), previous_state)
            return last_result

        return self._process_payload(self.client.collect_state_payload(), previous_state)
