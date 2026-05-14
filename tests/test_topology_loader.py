"""Tests for loading normalized data-driven topology files."""

from pathlib import Path

import pytest

from src.topology.topology_loader import load_topology_definition


def test_load_geant_subset_definition() -> None:
    path = Path("data/topologies/geant_subset.json")

    definition = load_topology_definition(path)

    assert definition.name == "geant_subset"
    assert len(definition.switches) == 8
    assert len(definition.hosts) == 8
    assert len(definition.links) == 7
    assert definition.switches[0].city == "London"
    assert definition.switches[0].latitude == 51.5072
    assert definition.links[2].label == "Paris-Frankfurt"
    assert definition.links[2].distance_km == 478.0
    assert definition.scenario_targets["recovery_scenario"] == ["s2", "s4"]


def test_load_topology_definition_rejects_unknown_scenario_switch(tmp_path) -> None:
    topology_file = tmp_path / "broken.json"
    topology_file.write_text(
        """
        {
          "name": "broken",
          "switches": [{"name": "s1", "dpid": "1"}],
          "hosts": [{"name": "h1", "switch": "s1", "ip": "10.0.0.1/24", "mac": "00:00:00:00:00:01"}],
          "links": [],
          "scenario_targets": {"single_link_failure": ["s1", "s2"]}
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_topology_definition(topology_file)


def test_backbone_definition_separates_modeled_and_active_links() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_backbone_8cities.json"))

    assert definition.name == "geant_backbone_8cities"
    assert len(definition.links) == 10
    assert len(definition.active_links()) == 7
    assert any(link.label == "Paris-Amsterdam" and link.enabled is False for link in definition.links)
    assert any(link.label == "Amsterdam-Frankfurt" and link.enabled is False for link in definition.links)


def test_backbone_stage1_enables_first_ring_link() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_backbone_8cities_stage1.json"))

    assert len(definition.active_links()) == 8
    assert any(link.label == "Paris-Amsterdam" and link.enabled is True for link in definition.links)


def test_backbone_stage2_enables_second_ring_link() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_backbone_8cities_stage2.json"))

    assert len(definition.active_links()) == 9
    assert any(link.label == "Paris-Amsterdam" and link.enabled is True for link in definition.links)
    assert any(link.label == "Amsterdam-Frankfurt" and link.enabled is True for link in definition.links)


def test_backbone_stage3_enables_all_modeled_links() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_backbone_8cities_stage3.json"))

    assert len(definition.active_links()) == 10
    assert all(link.enabled is True for link in definition.links)
    assert any(link.label == "Vienna-Milan" for link in definition.links)


def test_load_geant2012_core12_definition() -> None:
    definition = load_topology_definition(Path("data/topologies/generated/geant2012_core12.json"))

    assert definition.name == "geant2012_core12"
    assert len(definition.switches) == 12
    assert len(definition.hosts) == 12
    assert len(definition.links) == 16
    assert any(switch.city == "United Kingdom" for switch in definition.switches)
    assert any(link.label == "FR-UK" for link in definition.links)
    assert definition.scenario_targets["multi_fault_scenario"] == [["s3", "s14"], ["s3", "s16"]]
