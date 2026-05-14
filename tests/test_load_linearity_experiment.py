"""Tests for background-load linearity experiment helpers."""

import csv
import json
from pathlib import Path

from src.topology.topology_loader import load_topology_definition
from src.twin.experiment_runner import ExperimentRecord, write_experiment_results
from src.twin.load_linearity_experiment import (
    _single_load_output_csv,
    _target_link_bandwidth_mbps,
    assemble_load_linearity_outputs,
    parse_args,
)


def test_target_link_bandwidth_uses_scenario_target_link() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_backbone_8cities_stage3.json"))

    bandwidth_mbps = _target_link_bandwidth_mbps(definition, "recovery_scenario")

    assert bandwidth_mbps == 100.0


def test_parse_args_supports_multiple_load_levels() -> None:
    args = parse_args(
        [
            "--topology-file",
            "data/topologies/geant_backbone_8cities_stage3.json",
            "--scenario",
            "recovery_scenario",
            "--repeat",
            "5",
            "--load-levels",
            "10",
            "30",
            "50",
            "80",
            "--single-load-level",
            "30",
            "--execution-schedule-file",
            "data/exports/load_linearity_schedule.json",
        ]
    )

    assert args.topology_file == Path("data/topologies/geant_backbone_8cities_stage3.json")
    assert args.scenario == "recovery_scenario"
    assert args.repeat == 5
    assert args.load_levels == [10, 30, 50, 80]
    assert args.single_load_level == 30
    assert args.execution_schedule_file == Path("data/exports/load_linearity_schedule.json")


def test_assemble_outputs_merges_per_load_exports(tmp_path: Path) -> None:
    prefix = tmp_path / "load_linearity_recovery"
    csv_10 = _single_load_output_csv(prefix, 10)
    csv_30 = _single_load_output_csv(prefix, 30)

    record_10 = ExperimentRecord(
        scenario_name="recovery_scenario",
        fault_injection_timestamp="2026-01-01T00:00:00+00:00",
        detection_timestamp="2026-01-01T00:00:01+00:00",
        recovery_timestamp="2026-01-01T00:00:03+00:00",
        detection_delay=1.0,
        recovery_delay=3.0,
        poll_interval=2.0,
        notes="10pct",
        background_traffic="iperf_tcp",
        background_load_percent=10,
        background_target_bandwidth_mbps=10.0,
        controller_app="src.controller.topology_aware_switch",
        repeat_index=1,
        configured_repeat_count=2,
    )
    record_30 = ExperimentRecord(
        scenario_name="recovery_scenario",
        fault_injection_timestamp="2026-01-01T00:01:00+00:00",
        detection_timestamp="2026-01-01T00:01:02+00:00",
        recovery_timestamp="2026-01-01T00:01:05+00:00",
        detection_delay=2.0,
        recovery_delay=5.0,
        poll_interval=2.0,
        notes="30pct",
        background_traffic="iperf_tcp",
        background_load_percent=30,
        background_target_bandwidth_mbps=30.0,
        controller_app="src.controller.topology_aware_switch",
        repeat_index=1,
        configured_repeat_count=2,
    )

    write_experiment_results([record_10], csv_10)
    write_experiment_results([record_30], csv_30)

    resource_fieldnames = [
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
    for load_percent, csv_path in ((10, csv_10), (30, csv_30)):
        resource_log = csv_path.with_name(f"{csv_path.stem}_resource_logs.csv")
        with resource_log.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=resource_fieldnames)
            writer.writeheader()
            writer.writerow(
                {
                    "timestamp": f"2026-01-01T00:00:0{load_percent // 10}+00:00",
                    "scenario_name": "recovery_scenario",
                    "background_traffic": "iperf_tcp",
                    "background_load_percent": str(load_percent),
                    "repeat_index": "1",
                    "event_name": "",
                    "process_name": "ryu_controller",
                    "pid": "123",
                    "cpu_percent": "50.0",
                    "rss_bytes": "1024",
                    "ctx_switches_voluntary": "10",
                    "ctx_switches_involuntary": "2",
                    "ctx_switches_total": "12",
                    "ctx_switches_delta": "1",
                    "ctx_switches_per_second": "5.0",
                }
            )

    schedule_file = tmp_path / "execution_schedule.json"
    schedule_file.write_text(
        json.dumps(
            [
                {
                    "repeat_index": 1,
                    "run_order": 2,
                    "load_percent": 10,
                    "output_csv": str(csv_10),
                    "configured_repeat_count": 2,
                },
                {
                    "repeat_index": 2,
                    "run_order": 1,
                    "load_percent": 30,
                    "output_csv": str(csv_30),
                    "configured_repeat_count": 2,
                },
            ]
        ),
        encoding="utf-8",
    )

    outputs = assemble_load_linearity_outputs(
        topology_file=Path("data/topologies/geant_backbone_8cities_stage3.json"),
        scenario_name="recovery_scenario",
        repeat=2,
        load_levels=[10, 30],
        output_prefix=prefix,
        input_csvs=[csv_10, csv_30],
        execution_schedule_file=schedule_file,
    )

    combined_csv = Path(outputs["records_csv"])
    combined_rows = list(csv.DictReader(combined_csv.open("r", encoding="utf-8", newline="")))
    assert len(combined_rows) == 2
    assert combined_rows[0]["Run_Order"] == "2"
    assert combined_rows[0]["repeat_index"] == "1"
    assert combined_rows[1]["Run_Order"] == "1"
    assert combined_rows[1]["repeat_index"] == "2"

    resource_logs_csv = Path(outputs["resource_logs_csv"])
    resource_rows = list(csv.DictReader(resource_logs_csv.open("r", encoding="utf-8", newline="")))
    assert len(resource_rows) == 2

    manifest = json.loads(Path(outputs["manifest_json"]).read_text(encoding="utf-8"))
    assert manifest["execution_mode"] == "isolated_controller_restart"
    assert manifest["generated_csvs"] == [str(csv_10), str(csv_30)]
    assert manifest["execution_schedule_file"] == str(schedule_file)
