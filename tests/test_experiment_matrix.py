"""Tests for the repeated experiment matrix runner."""

import json
from pathlib import Path

from src.twin.config import AppConfig
from src.twin.experiment_matrix import _matrix_stem, _write_matrix_manifest, parse_args


def test_matrix_stem_combines_scenario_and_traffic() -> None:
    assert _matrix_stem("recovery_scenario", "icmp") == "minimal_demo_recovery_scenario_icmp"
    assert (
        _matrix_stem("recovery_scenario", "icmp", Path("data/topologies/generated/geant2012_core12.json"))
        == "geant2012_core12_recovery_scenario_icmp"
    )


def test_parse_args_uses_expected_defaults() -> None:
    args = parse_args([])

    assert args.output_prefix == Path("data/exports/experiment_matrix")
    assert args.repeat == 1
    assert args.topology_files is None
    assert args.scenarios == [
        "recovery_scenario",
        "link_flap_scenario",
        "multi_fault_scenario",
        "observation_degradation_scenario",
    ]
    assert args.traffic_profiles == ["none", "icmp"]


def test_parse_args_accepts_custom_matrix_subset() -> None:
    args = parse_args(
        [
            "--topology-file",
            "data/topologies/geant_backbone_8cities_stage3.json",
            "--repeat",
            "3",
            "--output-prefix",
            "data/exports/custom_matrix",
            "--scenarios",
            "recovery_scenario",
            "multi_fault_scenario",
            "--traffic-profiles",
            "iperf_tcp",
        ]
    )

    assert args.topology_file == Path("data/topologies/geant_backbone_8cities_stage3.json")
    assert args.repeat == 3
    assert args.output_prefix == Path("data/exports/custom_matrix")
    assert args.scenarios == ["recovery_scenario", "multi_fault_scenario"]
    assert args.traffic_profiles == ["iperf_tcp"]


def test_parse_args_accepts_multiple_topology_files() -> None:
    args = parse_args(
        [
            "--topology-files",
            "data/topologies/geant_backbone_8cities_stage3.json",
            "data/topologies/generated/geant2012_core12.json",
        ]
    )

    assert args.topology_files == [
        Path("data/topologies/geant_backbone_8cities_stage3.json"),
        Path("data/topologies/generated/geant2012_core12.json"),
    ]


def test_write_matrix_manifest_includes_traceable_metadata(tmp_path: Path) -> None:
    manifest_path = _write_matrix_manifest(
        manifest_path=tmp_path / "manifest.json",
        topology_files=[
            Path("data/topologies/geant_backbone_8cities_stage3.json"),
            Path("data/topologies/generated/geant2012_core12.json"),
        ],
        scenarios=["recovery_scenario"],
        traffic_profiles=["none", "icmp"],
        repeat=3,
        background_ping_interval=0.2,
        output_prefix=tmp_path / "matrix",
        generated_csvs=["a.csv", "b.csv"],
        app_config=AppConfig(),
        records_csv=tmp_path / "matrix.csv",
        records_json=tmp_path / "matrix.json",
        summary_csv=tmp_path / "matrix_summary.csv",
        summary_json=tmp_path / "matrix_summary.json",
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["repeat"] == 3
    assert payload["controller_app"] == "src.controller.topology_aware_switch"
    assert payload["topology_files"] == [
        "data/topologies/geant_backbone_8cities_stage3.json",
        "data/topologies/generated/geant2012_core12.json",
    ]
    assert payload["summary_csv"].endswith("matrix_summary.csv")
