"""Tests for combining controller-comparison summary files."""

import csv
import json
from pathlib import Path

from src.twin.controller_comparison import load_summary_rows, parse_args, write_combined_summary


def test_load_summary_rows_sorts_by_controller_and_topology(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    rows = [
        {
            "scenario_name": "recovery_scenario",
            "topology_name": "geant",
            "controller_app": "src.controller.tree_routing_switch",
            "background_traffic": "none",
            "target_link": "Paris-Frankfurt",
        },
        {
            "scenario_name": "recovery_scenario",
            "topology_name": "geant",
            "controller_app": "src.controller.topology_aware_switch",
            "background_traffic": "none",
            "target_link": "Paris-Frankfurt",
        },
    ]
    for path, row in zip((first, second), rows, strict=True):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)

    loaded = load_summary_rows([first, second])

    assert [row["controller_app"] for row in loaded] == [
        "src.controller.topology_aware_switch",
        "src.controller.tree_routing_switch",
    ]


def test_write_combined_summary_writes_csv_and_json(tmp_path: Path) -> None:
    rows = [
        {
            "scenario_name": "recovery_scenario",
            "topology_name": "geant",
            "controller_app": "src.controller.topology_aware_switch",
            "background_traffic": "none",
            "target_link": "Paris-Frankfurt",
        }
    ]

    csv_path, json_path = write_combined_summary(rows, tmp_path / "combined.csv", tmp_path / "combined.json")

    assert csv_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))[0]["controller_app"] == "src.controller.topology_aware_switch"


def test_parse_args_accepts_multiple_inputs() -> None:
    args = parse_args(
        [
            "--inputs",
            "a.csv",
            "b.csv",
            "--output-csv",
            "combined.csv",
            "--output-json",
            "combined.json",
        ]
    )

    assert args.inputs == [Path("a.csv"), Path("b.csv")]
    assert args.output_csv == Path("combined.csv")
    assert args.output_json == Path("combined.json")
