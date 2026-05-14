"""Batch runner for sync-mode comparison experiments."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from src.twin.config import AppConfig
from src.twin.experiment_runner import (
    BackgroundTrafficConfig,
    ExperimentRecord,
    run_scenario,
    summarize_experiment_records,
    write_experiment_results,
    write_experiment_statistics,
)


DEFAULT_SYNC_MODES = ["polling", "event_driven", "hybrid"]
DEFAULT_SCENARIOS = ["single_link_failure", "recovery_scenario"]


def _topology_slug(topology_file: Path | None) -> str:
    return topology_file.stem if topology_file is not None else "minimal_demo"


def _comparison_stem(scenario_name: str, sync_mode: str, topology_file: Path | None = None) -> str:
    return f"{_topology_slug(topology_file)}_{scenario_name}_{sync_mode}"


def _write_comparison_manifest(
    *,
    manifest_path: Path,
    topology_file: Path | None,
    scenarios: list[str],
    sync_modes: list[str],
    repeat: int,
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
        "topology_file": str(topology_file) if topology_file is not None else "minimal_demo",
        "scenarios": scenarios,
        "sync_modes": sync_modes,
        "repeat": repeat,
        "poll_interval_seconds": app_config.polling_interval_seconds,
        "hybrid_polling_interval_seconds": app_config.hybrid_polling_interval_seconds,
        "controller_app": app_config.controller_app,
        "records_csv": str(records_csv),
        "records_json": str(records_json),
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "generated_csvs": generated_csvs,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def run_sync_mode_comparison(
    *,
    topology_file: Path | None,
    scenarios: list[str],
    sync_modes: list[str],
    repeat: int,
    output_prefix: Path,
    config: AppConfig | None = None,
) -> dict[str, object]:
    """Run the same scenarios across multiple twin sync modes."""

    base_config = config or AppConfig()
    base_config.ensure_directories()

    all_records: list[ExperimentRecord] = []
    generated_csvs: list[str] = []

    for sync_mode in sync_modes:
        mode_config = replace(base_config, sync_mode=sync_mode)
        mode_config.ensure_directories()
        for scenario_name in scenarios:
            output_csv = output_prefix.parent / f"{_comparison_stem(scenario_name, sync_mode, topology_file)}.csv"
            generated_csvs.append(str(output_csv))
            all_records.extend(
                run_scenario(
                    scenario_name=scenario_name,
                    config=mode_config,
                    csv_path=output_csv,
                    topology_file=topology_file,
                    background_traffic=BackgroundTrafficConfig(profile="none"),
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
        topology_file=topology_file,
        scenarios=scenarios,
        sync_modes=sync_modes,
        repeat=repeat,
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
    """Parse CLI args for sync-mode comparison runs."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology-file", type=Path, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--output-prefix", type=Path, default=Path("data/exports/sync_mode_comparison"))
    parser.add_argument("--scenarios", nargs="+", default=DEFAULT_SCENARIOS, choices=DEFAULT_SCENARIOS)
    parser.add_argument("--sync-modes", nargs="+", default=DEFAULT_SYNC_MODES, choices=DEFAULT_SYNC_MODES)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for sync-mode comparisons."""

    args = parse_args(argv)
    outputs = run_sync_mode_comparison(
        topology_file=args.topology_file,
        scenarios=args.scenarios,
        sync_modes=args.sync_modes,
        repeat=args.repeat,
        output_prefix=args.output_prefix,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
