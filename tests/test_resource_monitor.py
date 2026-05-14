"""Tests for resource monitoring helpers."""

from __future__ import annotations

import csv
import os
import time

from src.twin.resource_monitor import ProcessSpec, ResourceMonitor


def test_resource_monitor_writes_context_switch_columns(tmp_path) -> None:
    csv_path = tmp_path / "resource_logs.csv"
    monitor = ResourceMonitor(
        csv_path=csv_path,
        process_specs=[ProcessSpec(name="self", pid=os.getpid())],
        interval=0.01,
        base_metadata={"scenario_name": "demo", "background_traffic": "none", "background_load_percent": "", "repeat_index": 1},
    )

    monitor.start()
    time.sleep(0.05)
    monitor.mark_event("fault_injected")
    monitor.stop()

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    sample_rows = [row for row in rows if row["process_name"] == "self"]
    assert sample_rows
    assert "ctx_switches_total" in sample_rows[0]
    assert "ctx_switches_delta" in sample_rows[0]
    assert "ctx_switches_per_second" in sample_rows[0]


def test_resource_monitor_event_rows_leave_context_switch_fields_blank(tmp_path) -> None:
    csv_path = tmp_path / "resource_logs.csv"
    monitor = ResourceMonitor(
        csv_path=csv_path,
        process_specs=[ProcessSpec(name="self", pid=os.getpid())],
        interval=0.01,
        base_metadata={"scenario_name": "demo", "background_traffic": "none", "background_load_percent": "", "repeat_index": 1},
    )

    monitor.start()
    monitor.mark_event("fault_injected")
    monitor.stop()

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    event_rows = [row for row in rows if row["event_name"] == "fault_injected"]
    assert len(event_rows) == 1
    assert event_rows[0]["ctx_switches_total"] == ""
    assert event_rows[0]["ctx_switches_per_second"] == ""
