"""Service layer that coordinates polling, storage, and presentation access."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from src.controller.ryu_api_client import RyuAPIClient
from src.topology.topology_loader import TopologyDefinition
from src.twin.anomaly_detector import JsonLineAnomalyStore, TrafficAnomalyDetector
from src.twin.config import AppConfig
from src.twin.event_sync_engine import EventSyncEngine
from src.twin.fidelity import FidelityReport, compute_fidelity_report
from src.twin.storage import InMemoryStateStore, JsonLineEventStore, JsonSnapshotStore
from src.twin.sync_engine import SyncEngine, SyncResult, build_network_state


@dataclass(slots=True)
class TwinServiceStatus:
    """Serializable summary of the service health."""

    running: bool
    has_state: bool
    last_sync_timestamp: str | None
    last_error_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "has_state": self.has_state,
            "last_sync_timestamp": self.last_sync_timestamp,
            "last_error_count": self.last_error_count,
        }


class TwinService:
    """High-level service used by the Flask API and experiment scripts."""

    def __init__(
        self,
        config: AppConfig,
        client: RyuAPIClient | None = None,
        truth_client: RyuAPIClient | None = None,
        topology_definition: TopologyDefinition | None = None,
    ) -> None:
        self.config = config
        self.config.ensure_directories()
        self.state_store = InMemoryStateStore()
        self.snapshot_store = JsonSnapshotStore(config.snapshots_dir)
        self.event_store = JsonLineEventStore(config.events_log_path)
        self.anomaly_store = JsonLineAnomalyStore(config.anomaly_log_path)
        self.anomaly_detector = TrafficAnomalyDetector()
        self.client = client or RyuAPIClient(base_url=config.ryu_base_url)
        self.truth_client = truth_client or getattr(self.client, "base_client", self.client)
        self.topology_definition = topology_definition
        if config.sync_mode == "polling":
            self.sync_engine = SyncEngine(
                client=self.client,
                state_store=self.state_store,
                snapshot_store=self.snapshot_store,
                event_store=self.event_store,
                topology_definition=topology_definition,
            )
        else:
            self.sync_engine = EventSyncEngine(
                client=self.client,
                state_store=self.state_store,
                snapshot_store=self.snapshot_store,
                event_store=self.event_store,
                topology_definition=topology_definition,
                event_stream_path=config.event_stream_path,
                event_wait_timeout_seconds=config.event_queue_wait_seconds,
                fallback_poll_interval_seconds=(
                    config.hybrid_polling_interval_seconds if config.sync_mode == "hybrid" else None
                ),
                event_settle_timeout_seconds=config.event_settle_timeout_seconds,
                event_settle_poll_seconds=config.event_settle_poll_seconds,
            )
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_result: SyncResult | None = None

    def sync_once(self) -> SyncResult:
        """Run one guarded sync cycle."""

        with self._lock:
            previous_state = self.state_store.get_current_state()
            self._last_result = self.sync_engine.sync_once()
            anomalies = self.anomaly_detector.check(self._last_result.state, previous_state)
            self.anomaly_store.append_many(anomalies)
            return self._last_result

    def ensure_state(self) -> None:
        """Populate an initial state snapshot when needed."""

        if self.state_store.get_current_state() is None:
            self.sync_once()

    def start(self) -> None:
        """Start the background polling thread if it is not running yet."""

        if self.is_running:
            return

        self._stop_event.clear()

        def loop() -> None:
            while not self._stop_event.is_set():
                self.sync_once()
                if isinstance(self.sync_engine, SyncEngine):
                    if self._stop_event.wait(self.config.polling_interval_seconds):
                        return

        self._thread = threading.Thread(target=loop, name="twin-sync-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread."""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_state(self) -> dict[str, Any]:
        """Return the latest twin state as a serializable dict."""

        self.ensure_state()
        state = self.state_store.get_current_state()
        return state.to_dict() if state is not None else {}

    def get_topology(self) -> dict[str, Any]:
        """Return a topology-oriented view derived from the current state."""

        state = self.get_state()
        return {
            "timestamp": state.get("timestamp"),
            "switches": [
                {
                    "dpid": switch["dpid"],
                    "name": switch["name"],
                    "city": switch.get("city"),
                    "country": switch.get("country"),
                    "latitude": switch.get("latitude"),
                    "longitude": switch.get("longitude"),
                    "flow_count": switch["flow_count"],
                }
                for switch in state.get("switches", [])
            ],
            "links": [
                {
                    "link_id": link["link_id"],
                    "src_dpid": link["src_dpid"],
                    "dst_dpid": link["dst_dpid"],
                    "is_up": link["is_up"],
                    "label": link.get("label"),
                    "distance_km": link.get("distance_km"),
                    "bandwidth_mbps": link.get("bandwidth_mbps"),
                    "latency_ms": link.get("latency_ms"),
                }
                for link in state.get("links", [])
            ],
            "hosts": state.get("hosts", []),
        }

    def get_events(self, limit: int = 20) -> list[dict[str, object]]:
        """Return recent structured events."""

        return self.event_store.load_recent(limit=limit)

    def get_anomalies(self, limit: int = 20) -> list[dict[str, object]]:
        """Return recent anomaly alerts."""

        return self.anomaly_store.load_recent(limit=limit)

    def get_fidelity_report(self) -> FidelityReport:
        """Return the current twin-vs-controller fidelity report."""

        self.ensure_state()
        twin_state = self.state_store.get_current_state()
        if twin_state is None:
            raise RuntimeError("Twin state is unavailable")

        payload = self.truth_client.collect_state_payload()
        truth_state = build_network_state(
            payload,
            previous_state=None,
            preserve_previous_links=False,
            switch_metadata_by_dpid=self.topology_definition.switches_by_dpid() if self.topology_definition else None,
            link_metadata_by_dpid_pair=(
                self.topology_definition.link_metadata_by_dpid_pair() if self.topology_definition else None
            ),
        )
        return compute_fidelity_report(twin_state, truth_state)

    def get_fidelity(self) -> dict[str, Any]:
        """Return a serializable fidelity snapshot."""

        return self.get_fidelity_report().to_dict()

    def health(self) -> dict[str, Any]:
        """Return a serializable service health snapshot."""

        last_result = self._last_result
        status = TwinServiceStatus(
            running=self.is_running,
            has_state=self.state_store.get_current_state() is not None,
            last_sync_timestamp=last_result.state.timestamp if last_result else None,
            last_error_count=len(last_result.errors) if last_result else 0,
        )
        return status.to_dict()
