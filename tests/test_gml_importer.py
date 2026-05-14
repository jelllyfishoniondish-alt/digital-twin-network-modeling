"""Tests for importing Topology Zoo style GML files."""

from pathlib import Path

from src.topology.importers.gml_importer import import_gml_topology, parse_args


def test_import_gml_topology_generates_internal_json_shape() -> None:
    topology = import_gml_topology(Path("data/topologies/raw/geant_sample.gml"), topology_name="geant_sample_gml")

    assert topology["name"] == "geant_sample_gml"
    assert len(topology["switches"]) == 3
    assert len(topology["hosts"]) == 3
    assert len(topology["links"]) == 2
    assert topology["switches"][0]["city"] == "Frankfurt"
    assert topology["links"][0]["label"] == "London-Paris"
    assert topology["links"][0]["bandwidth_mbps"] == 10000
    assert topology["scenario_targets"]["multi_fault_scenario"] == [["s2", "s3"], ["s3", "s1"]]


def test_parse_args_accepts_input_output_and_name() -> None:
    args = parse_args(
        [
            "--input",
            "data/topologies/raw/geant_sample.gml",
            "--output",
            "data/topologies/generated/geant_sample_gml.json",
            "--name",
            "geant_sample_gml",
        ]
    )

    assert args.input == Path("data/topologies/raw/geant_sample.gml")
    assert args.output == Path("data/topologies/generated/geant_sample_gml.json")
    assert args.name == "geant_sample_gml"
