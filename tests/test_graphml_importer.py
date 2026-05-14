"""Tests for importing Topology Zoo style GraphML files."""

from pathlib import Path

from src.topology.importers.graphml_importer import import_graphml_topology, parse_args


def test_import_graphml_topology_generates_internal_json_shape() -> None:
    topology = import_graphml_topology(Path("data/topologies/raw/geant_sample.graphml"), topology_name="geant_sample")

    assert topology["name"] == "geant_sample"
    assert len(topology["switches"]) == 3
    assert len(topology["hosts"]) == 3
    assert len(topology["links"]) == 2
    assert topology["switches"][0]["city"] == "Frankfurt"
    assert topology["switches"][1]["city"] == "London"
    assert topology["links"][0]["label"] == "London-Paris"
    assert topology["links"][0]["bandwidth_mbps"] == 10000
    assert topology["scenario_targets"]["recovery_scenario"] == ["s2", "s3"]


def test_parse_args_accepts_input_output_and_name() -> None:
    args = parse_args(
        [
            "--input",
            "data/topologies/raw/geant_sample.graphml",
            "--output",
            "data/topologies/generated/geant_sample.json",
            "--name",
            "geant_sample",
        ]
    )

    assert args.input == Path("data/topologies/raw/geant_sample.graphml")
    assert args.output == Path("data/topologies/generated/geant_sample.json")
    assert args.name == "geant_sample"
