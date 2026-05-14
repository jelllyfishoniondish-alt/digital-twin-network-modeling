"""Tests for building connected subsets from imported topology JSON."""

from pathlib import Path

import pytest

from src.topology.subset_builder import build_topology_subset, parse_args
from src.topology.topology_loader import load_topology_definition


def test_build_topology_subset_generates_connected_internal_topology(tmp_path: Path) -> None:
    output_path = tmp_path / "geant2012_core12.json"

    build_topology_subset(
        source_path=Path("data/topologies/generated/geant2012_full_imported.json"),
        output_path=output_path,
        selected_switches=["s1", "s3", "s5", "s7", "s8", "s13", "s14", "s16", "s20", "s30", "s36", "s40"],
        topology_name="geant2012_core12",
        description="12-node connected core subset derived from Geant2012.",
    )

    definition = load_topology_definition(output_path)

    assert definition.name == "geant2012_core12"
    assert len(definition.switches) == 12
    assert len(definition.hosts) == 12
    assert len(definition.links) == 16
    assert definition.provenance["subset_of"] == "geant2012_full"
    assert definition.scenario_targets["recovery_scenario"] == ["s3", "s14"]
    assert any(link.label == "FR-UK" for link in definition.links)
    assert any(switch.city == "Germany" for switch in definition.switches)


def test_build_topology_subset_rejects_unknown_switch_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown switch names"):
        build_topology_subset(
            source_path=Path("data/topologies/generated/geant2012_full_imported.json"),
            output_path=tmp_path / "broken.json",
            selected_switches=["s1", "missing"],
            topology_name="broken_subset",
        )


def test_parse_args_accepts_input_output_name_and_switches() -> None:
    args = parse_args(
        [
            "--input",
            "data/topologies/generated/geant2012_full_imported.json",
            "--output",
            "data/topologies/generated/geant2012_core12.json",
            "--name",
            "geant2012_core12",
            "--switches",
            "s1",
            "s8",
            "s13",
        ]
    )

    assert args.input == Path("data/topologies/generated/geant2012_full_imported.json")
    assert args.output == Path("data/topologies/generated/geant2012_core12.json")
    assert args.name == "geant2012_core12"
    assert args.switches == ["s1", "s8", "s13"]
