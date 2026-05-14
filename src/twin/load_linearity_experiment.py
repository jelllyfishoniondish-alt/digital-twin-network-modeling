"""Batch runner for background-load linearity experiments."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from src.topology.topology_loader import TopologyDefinition, load_topology_definition
from src.twin.config import AppConfig
from src.twin.experiment_runner import (
    BackgroundTrafficConfig,
    ExperimentRecord,
    _scenario_link_targets,
    run_scenario,
    summarize_experiment_records,
    write_experiment_results,
    write_experiment_statistics,
    write_experiment_summary,
)
from src.twin.plotting import build_delay_box_plot, build_load_scatter_plot, load_experiment_rows


DEFAULT_LOAD_LEVELS = [10, 30, 50, 80]


def _target_link_bandwidth_mbps(definition: TopologyDefinition, scenario_name: str) -> float:
    src_switch, dst_switch = _scenario_link_targets(scenario_name, definition)[0]
    link = definition.link_for_switch_pair(src_switch, dst_switch)
    if link is None:
        raise ValueError(f"Scenario target {src_switch}-{dst_switch} does not exist in topology {definition.name}.")
    return float(link.bandwidth_mbps)


def _single_load_output_csv(output_prefix: Path, load_percent: int) -> Path:
    return output_prefix.parent / f"{output_prefix.stem}_{load_percent}pct.csv"


def _load_schedule_index(
    execution_schedule: list[dict[str, object]] | None,
) -> dict[str, dict[str, int]]:
    if not execution_schedule:
        return {}
    index: dict[str, dict[str, int]] = {}
    for entry in execution_schedule:
        output_csv = str(entry.get("output_csv", ""))
        if not output_csv:
            continue
        index[output_csv] = {
            "repeat_index": int(entry.get("repeat_index", 1)),
            "configured_repeat_count": int(entry.get("configured_repeat_count", 1)),
            "Run_Order": int(entry.get("run_order", 0)),
        }
    return index


def _coerce_optional_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))


def _coerce_optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _coerce_optional_str(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    return value


def _experiment_record_from_row(row: dict[str, str]) -> ExperimentRecord:
    return ExperimentRecord(
        scenario_name=row["scenario_name"],
        fault_injection_timestamp=row["fault_injection_timestamp"],
        detection_timestamp=row["detection_timestamp"],
        recovery_timestamp=row["recovery_timestamp"],
        detection_delay=_coerce_optional_float(row.get("detection_delay")),
        recovery_delay=_coerce_optional_float(row.get("recovery_delay")),
        poll_interval=float(row["poll_interval"]),
        notes=row["notes"],
        sync_mode=_coerce_optional_str(row.get("sync_mode")),
        topology_name=_coerce_optional_str(row.get("topology_name")),
        topology_file=_coerce_optional_str(row.get("topology_file")),
        target_link=_coerce_optional_str(row.get("target_link")),
        target_src_city=_coerce_optional_str(row.get("target_src_city")),
        target_dst_city=_coerce_optional_str(row.get("target_dst_city")),
        target_distance_km=_coerce_optional_float(row.get("target_distance_km")),
        controller_app=_coerce_optional_str(row.get("controller_app")),
        background_traffic=row.get("background_traffic", "none") or "none",
        background_flow_count=int(row.get("background_flow_count", "0") or 0),
        background_load_percent=_coerce_optional_int(row.get("background_load_percent")),
        background_target_bandwidth_mbps=_coerce_optional_float(row.get("background_target_bandwidth_mbps")),
        controller_event_queue_depth_at_detection=_coerce_optional_int(
            row.get("controller_event_queue_depth_at_detection")
        ),
        controller_event_queue_depth_peak_until_detection=_coerce_optional_int(
            row.get("controller_event_queue_depth_peak_until_detection")
        ),
        controller_events_until_detection=_coerce_optional_int(row.get("controller_events_until_detection")),
        pre_fault_fidelity=_coerce_optional_float(row.get("pre_fault_fidelity")),
        post_fault_fidelity=_coerce_optional_float(row.get("post_fault_fidelity")),
        post_recovery_fidelity=_coerce_optional_float(row.get("post_recovery_fidelity")),
        fidelity_truth_source=_coerce_optional_str(row.get("fidelity_truth_source")),
        ground_truth_fault_timestamp=_coerce_optional_str(row.get("ground_truth_fault_timestamp")),
        ground_truth_recovery_timestamp=_coerce_optional_str(row.get("ground_truth_recovery_timestamp")),
        ground_truth_detection_lag=_coerce_optional_float(row.get("ground_truth_detection_lag")),
        ground_truth_recovery_lag=_coerce_optional_float(row.get("ground_truth_recovery_lag")),
        node_count=_coerce_optional_int(row.get("node_count")),
        link_count=_coerce_optional_int(row.get("link_count")),
        sync_duration_ms=_coerce_optional_float(row.get("sync_duration_ms")),
        api_call_count=_coerce_optional_int(row.get("api_call_count")),
        pre_fault_total_packets=_coerce_optional_int(row.get("pre_fault_total_packets")),
        pre_fault_total_bytes=_coerce_optional_int(row.get("pre_fault_total_bytes")),
        post_detection_total_packets=_coerce_optional_int(row.get("post_detection_total_packets")),
        post_detection_total_bytes=_coerce_optional_int(row.get("post_detection_total_bytes")),
        post_recovery_total_packets=_coerce_optional_int(row.get("post_recovery_total_packets")),
        post_recovery_total_bytes=_coerce_optional_int(row.get("post_recovery_total_bytes")),
        resource_log_file=_coerce_optional_str(row.get("resource_log_file")),
        Run_Order=_coerce_optional_int(row.get("Run_Order")),
        repeat_index=int(row.get("repeat_index", "1") or 1),
        configured_repeat_count=int(row.get("configured_repeat_count", "1") or 1),
    )


def _load_experiment_records(
    csv_path: Path,
    schedule_index: dict[str, dict[str, int]] | None = None,
) -> list[ExperimentRecord]:
    normalized_csv_path = str(csv_path)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        records = [_experiment_record_from_row(row) for row in csv.DictReader(handle)]
    schedule_row = (schedule_index or {}).get(normalized_csv_path)
    if schedule_row is None:
        return records
    for record in records:
        record.repeat_index = schedule_row["repeat_index"]
        record.configured_repeat_count = schedule_row["configured_repeat_count"]
        record.Run_Order = schedule_row["Run_Order"]
    return records


def _merge_resource_logs(csv_paths: list[Path], output_prefix: Path) -> Path | None:
    output_path = output_prefix.with_name(f"{output_prefix.stem}_resource_logs.csv")
    wrote_header = False
    row_count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as destination:
        writer: csv.DictWriter[str] | None = None
        for csv_path in csv_paths:
            resource_log_path = csv_path.with_name(f"{csv_path.stem}_resource_logs.csv")
            if not resource_log_path.exists():
                continue
            with resource_log_path.open("r", encoding="utf-8", newline="") as source:
                reader = csv.DictReader(source)
                if reader.fieldnames is None:
                    continue
                if writer is None:
                    writer = csv.DictWriter(destination, fieldnames=reader.fieldnames)
                if not wrote_header:
                    writer.writeheader()
                    wrote_header = True
                for row in reader:
                    writer.writerow(row)
                    row_count += 1
    if row_count == 0:
        output_path.unlink(missing_ok=True)
        return None
    return output_path


def _write_manifest(
    *,
    manifest_path: Path,
    topology_file: Path,
    scenario_name: str,
    repeat: int,
    load_levels: list[int],
    target_link_bandwidth_mbps: float,
    records_csv: Path,
    records_json: Path,
    summary_csv: Path,
    summary_json: Path,
    scatter_plot: Path,
    box_plot: Path,
    generated_csvs: list[str],
    merged_resource_logs_csv: str | None,
    execution_mode: str,
    execution_schedule_file: str | None,
    app_config: AppConfig,
) -> Path:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "topology_file": str(topology_file),
        "scenario_name": scenario_name,
        "repeat": repeat,
        "load_levels": load_levels,
        "target_link_bandwidth_mbps": target_link_bandwidth_mbps,
        "controller_app": app_config.controller_app,
        "polling_interval_seconds": app_config.polling_interval_seconds,
        "records_csv": str(records_csv),
        "records_json": str(records_json),
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "scatter_plot": str(scatter_plot),
        "box_plot": str(box_plot),
        "generated_csvs": generated_csvs,
        "merged_resource_logs_csv": merged_resource_logs_csv,
        "execution_mode": execution_mode,
        "execution_schedule_file": execution_schedule_file,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def _write_combined_outputs(
    *,
    records: list[ExperimentRecord],
    topology_file: Path,
    scenario_name: str,
    repeat: int,
    load_levels: list[int],
    output_prefix: Path,
    target_link_bandwidth_mbps: float,
    generated_csvs: list[str],
    config: AppConfig,
    execution_mode: str,
    execution_schedule_file: str | None = None,
) -> dict[str, str | list[str]]:
    if not records:
        raise ValueError("records must not be empty")

    combined_csv = output_prefix.with_suffix(".csv")
    combined_json = output_prefix.with_suffix(".json")
    write_experiment_results(records, combined_csv)
    write_experiment_summary(records, combined_json)

    summary_rows = summarize_experiment_records(records)
    summary_csv, summary_json = write_experiment_statistics(
        summary_rows,
        output_prefix.with_name(f"{output_prefix.stem}_summary.csv"),
        output_prefix.with_name(f"{output_prefix.stem}_summary.json"),
    )

    rows = load_experiment_rows(combined_csv)
    scatter_plot = build_load_scatter_plot(
        rows,
        output_prefix.with_name(f"{output_prefix.stem}_scatter.png"),
        metric="detection",
    )
    box_plot = build_delay_box_plot(
        rows,
        output_prefix.with_name(f"{output_prefix.stem}_boxplot.png"),
        metric="detection",
    )
    merged_resource_logs = _merge_resource_logs([Path(path) for path in generated_csvs], output_prefix)
    manifest_path = _write_manifest(
        manifest_path=output_prefix.with_name(f"{output_prefix.stem}_manifest.json"),
        topology_file=topology_file,
        scenario_name=scenario_name,
        repeat=repeat,
        load_levels=load_levels,
        target_link_bandwidth_mbps=target_link_bandwidth_mbps,
        records_csv=combined_csv,
        records_json=combined_json,
        summary_csv=summary_csv,
        summary_json=summary_json,
        scatter_plot=scatter_plot,
        box_plot=box_plot,
        generated_csvs=generated_csvs,
        merged_resource_logs_csv=str(merged_resource_logs) if merged_resource_logs is not None else None,
        execution_mode=execution_mode,
        execution_schedule_file=execution_schedule_file,
        app_config=config,
    )

    return {
        "records_csv": str(combined_csv),
        "records_json": str(combined_json),
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "scatter_plot": str(scatter_plot),
        "box_plot": str(box_plot),
        "manifest_json": str(manifest_path),
        "resource_logs_csv": str(merged_resource_logs) if merged_resource_logs is not None else "",
        "generated_csvs": generated_csvs,
    }


def run_single_load_linearity_experiment(
    *,
    topology_file: Path,
    scenario_name: str,
    repeat: int,
    load_percent: int,
    output_prefix: Path,
    background_ping_interval: float = 0.2,
    config: AppConfig | None = None,
) -> dict[str, str | list[str]]:
    """Run one scenario at a single background load and export per-load outputs."""

    if repeat < 1:
        raise ValueError("repeat must be at least 1")

    app_config = config or AppConfig()
    app_config.ensure_directories()
    topology_definition = load_topology_definition(topology_file)
    target_link_bandwidth_mbps = _target_link_bandwidth_mbps(topology_definition, scenario_name)
    target_bandwidth_mbps = round(target_link_bandwidth_mbps * (load_percent / 100.0), 3)
    output_csv = _single_load_output_csv(output_prefix, load_percent)

    records = run_scenario(
        scenario_name=scenario_name,
        config=app_config,
        csv_path=output_csv,
        topology_file=topology_file,
        background_traffic=BackgroundTrafficConfig(
            profile="iperf_tcp",
            ping_interval_seconds=background_ping_interval,
            load_percent=load_percent,
            iperf_bandwidth_mbps=target_bandwidth_mbps,
        ),
        repeat=repeat,
    )

    return {
        "records_csv": str(output_csv),
        "records_json": str(output_csv.with_suffix(".json")),
        "summary_csv": str(output_csv.with_name(f"{output_csv.stem}_summary.csv")),
        "summary_json": str(output_csv.with_name(f"{output_csv.stem}_summary.json")),
        "resource_logs_csv": str(output_csv.with_name(f"{output_csv.stem}_resource_logs.csv")),
        "generated_csvs": [str(output_csv)],
        "samples": str(len(records)),
    }


def assemble_load_linearity_outputs(
    *,
    topology_file: Path,
    scenario_name: str,
    repeat: int,
    load_levels: list[int],
    output_prefix: Path,
    input_csvs: list[Path],
    config: AppConfig | None = None,
    execution_mode: str = "isolated_controller_restart",
    execution_schedule_file: Path | None = None,
) -> dict[str, str | list[str]]:
    """Aggregate per-load runs into a combined load-linearity export set."""

    if not input_csvs:
        raise ValueError("input_csvs must not be empty")

    app_config = config or AppConfig()
    app_config.ensure_directories()
    topology_definition = load_topology_definition(topology_file)
    target_link_bandwidth_mbps = _target_link_bandwidth_mbps(topology_definition, scenario_name)
    execution_schedule = None
    if execution_schedule_file is not None and execution_schedule_file.exists():
        execution_schedule = json.loads(execution_schedule_file.read_text(encoding="utf-8"))
    schedule_index = _load_schedule_index(execution_schedule)

    records: list[ExperimentRecord] = []
    for csv_path in input_csvs:
        records.extend(_load_experiment_records(csv_path, schedule_index))

    return _write_combined_outputs(
        records=records,
        topology_file=topology_file,
        scenario_name=scenario_name,
        repeat=repeat,
        load_levels=load_levels,
        output_prefix=output_prefix,
        target_link_bandwidth_mbps=target_link_bandwidth_mbps,
        generated_csvs=[str(path) for path in input_csvs],
        config=app_config,
        execution_mode=execution_mode,
        execution_schedule_file=str(execution_schedule_file) if execution_schedule_file is not None else None,
    )


def run_load_linearity_experiment(
    *,
    topology_file: Path,
    scenario_name: str,
    repeat: int,
    load_levels: list[int],
    output_prefix: Path,
    background_ping_interval: float = 0.2,
    config: AppConfig | None = None,
) -> dict[str, str | list[str]]:
    """Run one scenario at multiple background load levels and export combined outputs."""

    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    if not load_levels:
        raise ValueError("load_levels must not be empty")

    app_config = config or AppConfig()
    app_config.ensure_directories()
    topology_definition = load_topology_definition(topology_file)
    target_link_bandwidth_mbps = _target_link_bandwidth_mbps(topology_definition, scenario_name)

    generated_csvs: list[str] = []
    for load_percent in load_levels:
        run_single_load_linearity_experiment(
            topology_file=topology_file,
            scenario_name=scenario_name,
            repeat=repeat,
            load_percent=load_percent,
            output_prefix=output_prefix,
            background_ping_interval=background_ping_interval,
            config=app_config,
        )
        generated_csvs.append(str(_single_load_output_csv(output_prefix, load_percent)))

    records: list[ExperimentRecord] = []
    for csv_path in generated_csvs:
        records.extend(_load_experiment_records(Path(csv_path)))

    return _write_combined_outputs(
        records=records,
        topology_file=topology_file,
        scenario_name=scenario_name,
        repeat=repeat,
        load_levels=load_levels,
        output_prefix=output_prefix,
        target_link_bandwidth_mbps=target_link_bandwidth_mbps,
        generated_csvs=generated_csvs,
        config=app_config,
        execution_mode="shared_controller_session",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the load-linearity experiment runner."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology-file", type=Path, required=True)
    parser.add_argument(
        "--scenario",
        choices=[
            "single_link_failure",
            "recovery_scenario",
            "multi_fault_scenario",
            "link_flap_scenario",
            "observation_degradation_scenario",
        ],
        default="recovery_scenario",
    )
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--background-ping-interval", type=float, default=0.2)
    parser.add_argument("--output-prefix", type=Path, default=Path("data/exports/load_linearity"))
    parser.add_argument("--load-levels", type=int, nargs="+", default=DEFAULT_LOAD_LEVELS)
    parser.add_argument("--single-load-level", type=int, default=None)
    parser.add_argument("--aggregate-input-csvs", type=Path, nargs="+", default=None)
    parser.add_argument("--execution-schedule-file", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for load-linearity experiments."""

    args = parse_args(argv)
    if args.single_load_level is not None and args.aggregate_input_csvs is not None:
        raise SystemExit("--single-load-level and --aggregate-input-csvs cannot be used together.")

    if args.aggregate_input_csvs is not None:
        outputs = assemble_load_linearity_outputs(
            topology_file=args.topology_file,
            scenario_name=args.scenario,
            repeat=args.repeat,
            load_levels=args.load_levels,
            output_prefix=args.output_prefix,
            input_csvs=args.aggregate_input_csvs,
            execution_schedule_file=args.execution_schedule_file,
        )
    elif args.single_load_level is not None:
        outputs = run_single_load_linearity_experiment(
            topology_file=args.topology_file,
            scenario_name=args.scenario,
            repeat=args.repeat,
            load_percent=args.single_load_level,
            output_prefix=args.output_prefix,
            background_ping_interval=args.background_ping_interval,
        )
    else:
        outputs = run_load_linearity_experiment(
            topology_file=args.topology_file,
            scenario_name=args.scenario,
            repeat=args.repeat,
            load_levels=args.load_levels,
            output_prefix=args.output_prefix,
            background_ping_interval=args.background_ping_interval,
        )

    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
