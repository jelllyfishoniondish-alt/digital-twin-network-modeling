"""Application configuration for the TER network digital twin PoC."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AppConfig:
    """Centralized configuration shared across topology, polling, and storage."""

    ryu_base_url: str = os.getenv("RYU_BASE_URL", "http://127.0.0.1:8080")
    controller_host: str = os.getenv("CONTROLLER_HOST", "127.0.0.1")
    controller_port: int = int(os.getenv("CONTROLLER_PORT", "6633"))
    controller_app: str = os.getenv("CONTROLLER_APP", "src.controller.topology_aware_switch")
    sync_mode: str = os.getenv("SYNC_MODE", "polling")
    polling_interval_seconds: float = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
    hybrid_polling_interval_seconds: float = float(os.getenv("HYBRID_POLL_INTERVAL_SECONDS", "10"))
    event_queue_wait_seconds: float = float(os.getenv("EVENT_QUEUE_WAIT_SECONDS", "0.5"))
    event_settle_timeout_seconds: float = float(os.getenv("EVENT_SETTLE_TIMEOUT_SECONDS", "1.0"))
    event_settle_poll_seconds: float = float(os.getenv("EVENT_SETTLE_POLL_SECONDS", "0.1"))
    initialization_timeout_seconds: float = field(
        default_factory=lambda: float(
            os.getenv("INITIALIZATION_TIMEOUT_SECONDS", os.getenv("SCENARIO_TIMEOUT_SECONDS", "20"))
        )
    )
    scenario_timeout_seconds: float = float(os.getenv("SCENARIO_TIMEOUT_SECONDS", "20"))
    save_snapshots: bool = os.getenv("SAVE_SNAPSHOTS", "true").lower() == "true"
    web_host: str = os.getenv("WEB_HOST", "127.0.0.1")
    web_port: int = int(os.getenv("WEB_PORT", "5000"))
    events_log_path: Path = PROJECT_ROOT / "data" / "events" / "events.jsonl"
    event_stream_path: Path = Path(os.getenv("EVENT_STREAM_PATH", str(PROJECT_ROOT / "data" / "events" / "controller_events.jsonl")))
    anomaly_log_path: Path = Path(os.getenv("ANOMALY_LOG_PATH", str(PROJECT_ROOT / "data" / "events" / "anomaly_alerts.jsonl")))
    snapshots_dir: Path = PROJECT_ROOT / "data" / "snapshots"
    exports_dir: Path = PROJECT_ROOT / "data" / "exports"
    plots_dir: Path = PROJECT_ROOT / "data" / "plots"

    def ensure_directories(self) -> None:
        """Create output directories required by the PoC."""

        if self.sync_mode not in {"polling", "event_driven", "hybrid"}:
            raise ValueError(f"Unsupported SYNC_MODE: {self.sync_mode}")
        self.events_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.event_stream_path.parent.mkdir(parents=True, exist_ok=True)
        self.anomaly_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.plots_dir.mkdir(parents=True, exist_ok=True)
