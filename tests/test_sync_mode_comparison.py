"""Tests for the sync-mode comparison runner."""

import json
from pathlib import Path

from src.twin.config import AppConfig
from src.twin.sync_mode_comparison import (
    _comparison_stem,
    _write_comparison_manifest,
    parse_args,
)


def test_comparison_stem_includes_sync_mode_and_topology() -> None:
    assert _comparison_stem("recovery_scenario", "hybrid") == "minimal_demo_recovery_scenario_hybrid"
    assert (
        _comparison_stem(
            "single_link_failure",
            "event_driven",
            Path("data/topologies/generated/geant2012_core12.json"),
        )
        == "geant2012_core12_single_link_failure_event_driven"
    )


def test_parse_args_uses_expected_defaults() -> None:
    args = parse_args([])

    assert args.output_prefix == Path("data/exports/sync_mode_comparison")
    assert args.repeat == 1
    assert args.scenarios == ["single_link_failure", "recovery_scenario"]
    assert args.sync_modes == ["polling", "event_driven", "hybrid"]


def test_parse_args_accepts_custom_values() -> None:
    args = parse_args(
        [
            "--topology-file",
            "data/topologies/geant_backbone_8cities_stage3.json",
            "--repeat",
            "3",
            "--scenarios",
            "recovery_scenario",
            "--sync-modes",
            "event_driven",
            "hybrid",
        ]
    )

    assert args.topology_file == Path("data/topologies/geant_backbone_8cities_stage3.json")
    assert args.repeat == 3
    assert args.scenarios == ["recovery_scenario"]
    assert args.sync_modes == ["event_driven", "hybrid"]


def test_write_comparison_manifest_includes_sync_mode_metadata(tmp_path: Path) -> None:
    manifest_path = _write_comparison_manifest(
        manifest_path=tmp_path / "manifest.json",
        topology_file=Path("data/topologies/geant_backbone_8cities_stage3.json"),
        scenarios=["single_link_failure", "recovery_scenario"],
        sync_modes=["polling", "event_driven", "hybrid"],
        repeat=2,
        output_prefix=tmp_path / "sync_mode_comparison",
        generated_csvs=["polling.csv", "hybrid.csv"],
        app_config=AppConfig(),
        records_csv=tmp_path / "comparison.csv",
        records_json=tmp_path / "comparison.json",
        summary_csv=tmp_path / "comparison_summary.csv",
        summary_json=tmp_path / "comparison_summary.json",
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["sync_modes"] == ["polling", "event_driven", "hybrid"]
    assert payload["controller_app"] == "src.controller.topology_aware_switch"
    assert payload["summary_csv"].endswith("comparison_summary.csv")
