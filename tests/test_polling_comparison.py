"""Tests for the polling-interval comparison runner."""

import json
from pathlib import Path

from src.twin.config import AppConfig
from src.twin.polling_comparison import (
    _comparison_stem,
    _poll_interval_slug,
    _write_comparison_manifest,
    parse_args,
)


def test_poll_interval_slug_formats_integer_and_fractional_values() -> None:
    assert _poll_interval_slug(1.0) == "poll1s"
    assert _poll_interval_slug(2.5) == "poll2p5s"


def test_comparison_stem_includes_poll_interval_and_topology() -> None:
    assert _comparison_stem("recovery_scenario", "icmp", 2.0) == "minimal_demo_recovery_scenario_icmp_poll2s"
    assert (
        _comparison_stem(
            "recovery_scenario",
            "icmp",
            4.0,
            Path("data/topologies/generated/geant2012_core12.json"),
        )
        == "geant2012_core12_recovery_scenario_icmp_poll4s"
    )


def test_parse_args_uses_expected_defaults() -> None:
    args = parse_args([])

    assert args.output_prefix == Path("data/exports/polling_comparison")
    assert args.repeat == 1
    assert args.polling_intervals == [1.0, 2.0, 4.0]
    assert args.scenarios == [
        "recovery_scenario",
        "link_flap_scenario",
        "multi_fault_scenario",
        "observation_degradation_scenario",
    ]
    assert args.traffic_profiles == ["none", "icmp"]


def test_parse_args_accepts_custom_intervals_and_topologies() -> None:
    args = parse_args(
        [
            "--topology-files",
            "data/topologies/geant_backbone_8cities_stage3.json",
            "data/topologies/generated/geant2012_core12.json",
            "--polling-intervals",
            "1",
            "4",
            "--scenarios",
            "recovery_scenario",
            "--traffic-profiles",
            "iperf_tcp",
        ]
    )

    assert args.topology_files == [
        Path("data/topologies/geant_backbone_8cities_stage3.json"),
        Path("data/topologies/generated/geant2012_core12.json"),
    ]
    assert args.polling_intervals == [1.0, 4.0]
    assert args.scenarios == ["recovery_scenario"]
    assert args.traffic_profiles == ["iperf_tcp"]


def test_write_comparison_manifest_includes_polling_metadata(tmp_path: Path) -> None:
    manifest_path = _write_comparison_manifest(
        manifest_path=tmp_path / "manifest.json",
        topology_files=[Path("data/topologies/geant_backbone_8cities_stage3.json")],
        scenarios=["recovery_scenario"],
        traffic_profiles=["none", "icmp"],
        polling_intervals=[1.0, 2.0, 4.0],
        repeat=3,
        background_ping_interval=0.2,
        output_prefix=tmp_path / "polling_compare",
        generated_csvs=["a.csv", "b.csv"],
        app_config=AppConfig(),
        records_csv=tmp_path / "comparison.csv",
        records_json=tmp_path / "comparison.json",
        summary_csv=tmp_path / "comparison_summary.csv",
        summary_json=tmp_path / "comparison_summary.json",
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["polling_intervals"] == [1.0, 2.0, 4.0]
    assert payload["controller_app"] == "src.controller.topology_aware_switch"
    assert payload["summary_csv"].endswith("comparison_summary.csv")
