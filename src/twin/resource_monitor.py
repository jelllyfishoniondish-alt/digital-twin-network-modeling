"""Resource monitoring helpers for experiment runs."""

from __future__ import annotations

import csv
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil


def _timestamp_now() -> str:
    return datetime.now().astimezone().isoformat()


@dataclass(slots=True)
class ProcessSpec:
    """Stable process metadata used for runtime resource sampling."""

    name: str
    pid: int


def find_ryu_process(controller_app: str | None = None) -> ProcessSpec | None:
    """Return the first matching Ryu controller process when available."""

    for process in psutil.process_iter(["pid", "cmdline"]):
        try:
            command = " ".join(process.info.get("cmdline") or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if "ryu-manager" not in command:
            continue
        if controller_app and controller_app not in command:
            continue
        return ProcessSpec(name="ryu_controller", pid=process.pid)
    return None


def build_default_process_specs(controller_app: str | None = None) -> list[ProcessSpec]:
    """Build the default set of monitored processes for one experiment run."""

    specs = [ProcessSpec(name="twin_core", pid=os.getpid())]
    ryu_process = find_ryu_process(controller_app=controller_app)
    if ryu_process is not None:
        specs.append(ryu_process)
    return specs


class ResourceMonitor:
    """Background sampler that appends process CPU and RSS usage to CSV."""

    def __init__(
        self,
        csv_path: Path,
        process_specs: list[ProcessSpec],
        interval: float = 0.1,
        base_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.csv_path = csv_path
        self.interval = interval
        self.base_metadata = dict(base_metadata or {})
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._processes = {
            spec.name: psutil.Process(spec.pid)
            for spec in process_specs
        }
        self._last_ctx_switch_totals: dict[str, int] = {}
        self._last_sample_monotonic: dict[str, float] = {}

    def start(self) -> None:
        """Start the sampling thread."""

        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()
        for process in self._processes.values():
            try:
                process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="resource-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the sampling thread and wait for it to finish."""

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.interval * 4, 1.0))
            self._thread = None

    def mark_event(self, event_name: str, **metadata: Any) -> None:
        """Append a timestamp marker row for later alignment with network events."""

        row = {
            "timestamp": metadata.pop("timestamp", _timestamp_now()),
            "event_name": event_name,
            "process_name": "",
            "pid": "",
            "cpu_percent": "",
            "rss_bytes": "",
            "ctx_switches_voluntary": "",
            "ctx_switches_involuntary": "",
            "ctx_switches_total": "",
            "ctx_switches_delta": "",
            "ctx_switches_per_second": "",
        }
        row.update(self.base_metadata)
        row.update(metadata)
        self._append_row(row)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            timestamp = _timestamp_now()
            for process_name, process in list(self._processes.items()):
                try:
                    cpu_percent = process.cpu_percent(interval=None)
                    rss_bytes = process.memory_info().rss
                    ctx_switches = process.num_ctx_switches()
                    pid = process.pid
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                ctx_switch_total = ctx_switches.voluntary + ctx_switches.involuntary
                last_total = self._last_ctx_switch_totals.get(process_name)
                delta = ctx_switch_total - last_total if last_total is not None else 0
                now_monotonic = time.monotonic()
                last_monotonic = self._last_sample_monotonic.get(process_name)
                elapsed = now_monotonic - last_monotonic if last_monotonic is not None else None
                ctx_switches_per_second = (delta / elapsed) if elapsed and elapsed > 0 else 0.0
                self._last_ctx_switch_totals[process_name] = ctx_switch_total
                self._last_sample_monotonic[process_name] = now_monotonic
                row = {
                    "timestamp": timestamp,
                    "event_name": "",
                    "process_name": process_name,
                    "pid": pid,
                    "cpu_percent": round(cpu_percent, 4),
                    "rss_bytes": rss_bytes,
                    "ctx_switches_voluntary": ctx_switches.voluntary,
                    "ctx_switches_involuntary": ctx_switches.involuntary,
                    "ctx_switches_total": ctx_switch_total,
                    "ctx_switches_delta": delta,
                    "ctx_switches_per_second": round(ctx_switches_per_second, 4),
                }
                row.update(self.base_metadata)
                self._append_row(row)
            self._stop_event.wait(self.interval)

    def _ensure_header(self) -> None:
        if self.csv_path.exists():
            return
        fieldnames = [
            "timestamp",
            "scenario_name",
            "background_traffic",
            "background_load_percent",
            "repeat_index",
            "event_name",
            "process_name",
            "pid",
            "cpu_percent",
            "rss_bytes",
            "ctx_switches_voluntary",
            "ctx_switches_involuntary",
            "ctx_switches_total",
            "ctx_switches_delta",
            "ctx_switches_per_second",
        ]
        with self.csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

    def _append_row(self, row: dict[str, Any]) -> None:
        with self._lock:
            with self.csv_path.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "timestamp",
                        "scenario_name",
                        "background_traffic",
                        "background_load_percent",
                        "repeat_index",
                        "event_name",
                        "process_name",
                        "pid",
                        "cpu_percent",
                        "rss_bytes",
                        "ctx_switches_voluntary",
                        "ctx_switches_involuntary",
                        "ctx_switches_total",
                        "ctx_switches_delta",
                        "ctx_switches_per_second",
                    ],
                )
                writer.writerow(row)
