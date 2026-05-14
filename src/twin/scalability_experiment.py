"""Scalability experiment runner for comparing topology size against sync cost."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.twin.config import AppConfig
from src.twin.experiment_runner import run_scenario
from src.twin.plotting import build_scalability_plot


DEFAULT_TOPOLOGIES = [
    ("minimal_topology", None),
    ("geant_subset", Path("data/topologies/geant_subset.json")),
    ("geant_backbone_8cities_stage3", Path("data/topologies/geant_backbone_8cities_stage3.json")),
    ("geant2012_core12", Path("data/topologies/generated/geant2012_core12.json")),
    ("geant2012_full_imported", Path("data/topologies/generated/geant2012_full_imported.json")),
]


def run_scalability_experiment(
    *,
    output_csv: Path,
    output_plot: Path,
    repeat: int = 3,
    config: AppConfig | None = None,
) -> dict[str, str]:
    """Run the single-link failure scenario across multiple topology sizes."""

    app_config = config or AppConfig()
    app_config.ensure_directories()

    rows: list[dict[str, object]] = []
    for topology_name, topology_file in DEFAULT_TOPOLOGIES:
        records = run_scenario(
            "single_link_failure",
            config=app_config,
            csv_path=app_config.exports_dir / f"{topology_name}_scalability_single_link_failure.csv",
            topology_file=topology_file,
            repeat=repeat,
        )
        for record in records:
            rows.append(
                {
                    "topology_name": topology_name,
                    "detection_delay": record.detection_delay,
                    "sync_duration_ms": record.sync_duration_ms,
                    "node_count": record.node_count,
                    "link_count": record.link_count,
                    "api_call_count": record.api_call_count,
                    "repeat_index": record.repeat_index,
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "topology_name",
                "detection_delay",
                "sync_duration_ms",
                "node_count",
                "link_count",
                "api_call_count",
                "repeat_index",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    build_scalability_plot(rows, output_plot)
    return {"csv": str(output_csv), "plot": str(output_plot)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-csv", type=Path, default=Path("data/exports/scalability.csv"))
    parser.add_argument("--output-plot", type=Path, default=Path("data/plots/scalability.png"))
    parser.add_argument("--repeat", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    outputs = run_scalability_experiment(
        output_csv=args.output_csv,
        output_plot=args.output_plot,
        repeat=args.repeat,
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
