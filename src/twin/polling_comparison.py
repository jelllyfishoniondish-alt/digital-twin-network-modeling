"""Batch runner for polling-interval comparison experiments."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from src.twin.config import AppConfig
from src.twin.experiment_matrix import DEFAULT_SCENARIOS, DEFAULT_TRAFFIC_PROFILES, SUPPORTED_TRAFFIC_PROFILES
from src.twin.experiment_runner import (
    BackgroundTrafficConfig,
    ExperimentRecord,
    run_scenario,
    summarize_experiment_records,
    write_experiment_results,
    write_experiment_statistics,
)


DEFAULT_POLLING_INTERVALS = [1.0, 2.0, 4.0]


def _topology_slug(topology_file: Path | None) -> str:
    return topology_file.stem if topology_file is not None else "minimal_demo"


def _poll_interval_slug(polling_interval: float) -> str:
    normalized = f"{polling_interval:g}".replace(".", "p")
    return f"poll{normalized}s"


def _comparison_stem(scenario_name: str, traffic_profile: str, polling_interval: float, topology_file: Path | None = None) -> str:
    return f"{_topology_slug(topology_file)}_{scenario_name}_{traffic_profile}_{_poll_interval_slug(polling_interval)}"


def _write_comparison_manifest(
    *,
    manifest_path: Path,
    topology_files: list[Path | None],
    scenarios: list[str],
    traffic_profiles: list[str],
    polling_intervals: list[float],
    repeat: int,
    background_ping_interval: float,
    output_prefix: Path,
    generated_csvs: list[str],
    app_config: AppConfig,
    records_csv: Path,
    records_json: Path,
    summary_csv: Path,
    summary_json: Path,
) -> Path:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "output_prefix": str(output_prefix),
        "topology_files": [str(path) if path is not None else "minimal_demo" for path in topology_files],
        "scenarios": scenarios,
        "traffic_profiles": traffic_profiles,
        "polling_intervals": polling_intervals,
        "repeat": repeat,
        "background_ping_interval": background_ping_interval,
        "controller_app": app_config.controller_app,
        "records_csv": str(records_csv),
        "records_json": str(records_json),
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "generated_csvs": generated_csvs,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def run_polling_interval_comparison(
    *,
    topology_files: list[Path | None],
    scenarios: list[str],
    traffic_profiles: list[str],
    polling_intervals: list[float],
    repeat: int,
    output_prefix: Path,
    background_ping_interval: float = 0.2,
    config: AppConfig | None = None,
) -> dict[str, object]:
    """Run the same experiment matrix across multiple polling intervals."""

    base_config = config or AppConfig()
    base_config.ensure_directories()

    all_records: list[ExperimentRecord] = []
    generated_csvs: list[str] = []

    for polling_interval in polling_intervals:
        interval_config = replace(base_config, polling_interval_seconds=polling_interval)
        interval_config.ensure_directories()
        for topology_file in topology_files:
            for scenario_name in scenarios:
                for traffic_profile in traffic_profiles:
                    output_csv = output_prefix.parent / (
                        f"{_comparison_stem(scenario_name, traffic_profile, polling_interval, topology_file)}.csv"
                    )
                    generated_csvs.append(str(output_csv))
                    all_records.extend(
                        run_scenario(
                            scenario_name=scenario_name,
                            config=interval_config,
                            csv_path=output_csv,
                            topology_file=topology_file,
                            background_traffic=BackgroundTrafficConfig(
                                profile=traffic_profile,
                                ping_interval_seconds=background_ping_interval,
                            ),
                            repeat=repeat,
                        )
                    )

    combined_csv = output_prefix.with_suffix(".csv")
    combined_json = output_prefix.with_suffix(".json")
    write_experiment_results(all_records, combined_csv)
    combined_json.write_text(
        json.dumps([record.to_row() for record in all_records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary_rows = summarize_experiment_records(all_records)
    summary_csv, summary_json = write_experiment_statistics(
        summary_rows,
        output_prefix.with_name(f"{output_prefix.stem}_summary.csv"),
        output_prefix.with_name(f"{output_prefix.stem}_summary.json"),
    )
    manifest_path = _write_comparison_manifest(
        manifest_path=output_prefix.with_name(f"{output_prefix.stem}_manifest.json"),
        topology_files=topology_files,
        scenarios=scenarios,
        traffic_profiles=traffic_profiles,
        polling_intervals=polling_intervals,
        repeat=repeat,
        background_ping_interval=background_ping_interval,
        output_prefix=output_prefix,
        generated_csvs=generated_csvs,
        app_config=base_config,
        records_csv=combined_csv,
        records_json=combined_json,
        summary_csv=summary_csv,
        summary_json=summary_json,
    )

    return {
        "records_csv": str(combined_csv),
        "records_json": str(combined_json),
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "manifest_json": str(manifest_path),
        "generated_csvs": generated_csvs,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for polling-interval comparisons."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology-file", type=Path, default=None)
    parser.add_argument("--topology-files", type=Path, nargs="+", default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--background-ping-interval", type=float, default=0.2)
    parser.add_argument("--polling-intervals", type=float, nargs="+", default=DEFAULT_POLLING_INTERVALS)
    parser.add_argument("--output-prefix", type=Path, default=Path("data/exports/polling_comparison"))
    parser.add_argument("--scenarios", nargs="+", default=DEFAULT_SCENARIOS, choices=DEFAULT_SCENARIOS)
    parser.add_argument(
        "--traffic-profiles",
        nargs="+",
        default=DEFAULT_TRAFFIC_PROFILES,
        choices=SUPPORTED_TRAFFIC_PROFILES,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for polling-interval comparison."""

    args = parse_args(argv)
    topology_files = args.topology_files or ([args.topology_file] if args.topology_file is not None else [None])
    outputs = run_polling_interval_comparison(
        topology_files=topology_files,
        scenarios=args.scenarios,
        traffic_profiles=args.traffic_profiles,
        polling_intervals=args.polling_intervals,
        repeat=args.repeat,
        output_prefix=args.output_prefix,
        background_ping_interval=args.background_ping_interval,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
