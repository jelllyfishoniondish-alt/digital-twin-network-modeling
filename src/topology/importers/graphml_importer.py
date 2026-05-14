"""Import Topology Zoo / TopoHub style GraphML files into the internal topology JSON format."""

from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from src.controller.ryu_api_client import normalize_dpid


GRAPHML_NAMESPACE = {"g": "http://graphml.graphdrawing.org/xmlns", "y": "http://www.yworks.com/xml/graphml"}


@dataclass(slots=True)
class ImportedNode:
    """Intermediate imported node representation."""

    raw_id: str
    label: str
    city: str | None
    country: str | None
    latitude: float | None
    longitude: float | None


@dataclass(slots=True)
class ImportedEdge:
    """Intermediate imported edge representation."""

    source: str
    target: str
    bandwidth_mbps: int
    label: str | None
    raw_data: dict[str, str]


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _canonical_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _graphml_key_map(root: ET.Element) -> dict[str, str]:
    key_map: dict[str, str] = {}
    for key in root.findall("g:key", GRAPHML_NAMESPACE):
        key_id = key.attrib.get("id")
        attr_name = key.attrib.get("attr.name")
        if key_id and attr_name:
            key_map[key_id] = attr_name
    return key_map


def _node_label(node_element: ET.Element, node_data: dict[str, str]) -> str:
    for candidate_key in ("label", "Label", "name", "Name"):
        if node_data.get(candidate_key):
            return node_data[candidate_key]

    for label in node_element.findall(".//y:NodeLabel", GRAPHML_NAMESPACE):
        text = (label.text or "").strip()
        if text:
            return text

    return node_element.attrib["id"]


def _node_city_country(label: str, node_data: dict[str, str]) -> tuple[str | None, str | None]:
    city = node_data.get("City") or node_data.get("city")
    country = node_data.get("Country") or node_data.get("country")
    if city is not None:
        return city, country
    if country is not None and re.fullmatch(r"[A-Z]{2,3}", label):
        return str(country), str(country)
    if "," in label:
        city_part, country_part = [part.strip() for part in label.split(",", 1)]
        return city_part or None, country or country_part or None
    return label or None, country


def _node_coordinates(node_data: dict[str, str]) -> tuple[float | None, float | None]:
    latitude = None
    longitude = None
    for key, value in node_data.items():
        canonical = _canonical_name(key)
        if canonical in {"latitude", "lat"}:
            latitude = _safe_float(value)
        elif canonical in {"longitude", "lon", "lng"}:
            longitude = _safe_float(value)
    return latitude, longitude


def _edge_bandwidth_mbps(edge_data: dict[str, str]) -> int:
    candidates = [
        edge_data.get("LinkSpeedRaw"),
        edge_data.get("capacity"),
        edge_data.get("Capacity"),
        edge_data.get("LinkSpeed"),
        edge_data.get("LinkLabel"),
    ]
    for candidate in candidates:
        numeric = _safe_float(candidate)
        if numeric is None or numeric <= 0:
            continue
        if numeric > 1_000_000:
            return max(1, int(numeric / 1_000_000))
        if numeric > 10_000:
            return max(1, int(numeric / 1_000))
        return max(1, int(numeric))
    return 100


def _edge_label(edge_data: dict[str, str], source_label: str, target_label: str) -> str:
    for candidate_key in ("label", "Label", "LinkLabel"):
        if edge_data.get(candidate_key):
            return edge_data[candidate_key]
    return f"{source_label}-{target_label}"


def _haversine_distance_km(
    latitude_a: float | None,
    longitude_a: float | None,
    latitude_b: float | None,
    longitude_b: float | None,
) -> float | None:
    if None in {latitude_a, longitude_a, latitude_b, longitude_b}:
        return None
    earth_radius_km = 6371.0
    lat_a = math.radians(latitude_a)  # type: ignore[arg-type]
    lon_a = math.radians(longitude_a)  # type: ignore[arg-type]
    lat_b = math.radians(latitude_b)  # type: ignore[arg-type]
    lon_b = math.radians(longitude_b)  # type: ignore[arg-type]

    delta_lat = lat_b - lat_a
    delta_lon = lon_b - lon_a
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_km * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _delay_from_distance(distance_km: float | None) -> float:
    if distance_km is None:
        return 10.0
    return round(distance_km / 200.0, 3)


def _parse_graphml_nodes(root: ET.Element, key_map: dict[str, str]) -> list[ImportedNode]:
    graph = root.find("g:graph", GRAPHML_NAMESPACE)
    if graph is None:
        raise ValueError("GraphML file does not contain a <graph> element.")

    imported_nodes: list[ImportedNode] = []
    for node_element in graph.findall("g:node", GRAPHML_NAMESPACE):
        node_data: dict[str, str] = {}
        for data_element in node_element.findall("g:data", GRAPHML_NAMESPACE):
            key_id = data_element.attrib.get("key")
            key_name = key_map.get(key_id or "", key_id or "")
            text = (data_element.text or "").strip()
            if text:
                node_data[key_name] = text
        label = _node_label(node_element, node_data)
        city, country = _node_city_country(label, node_data)
        latitude, longitude = _node_coordinates(node_data)
        imported_nodes.append(
            ImportedNode(
                raw_id=node_element.attrib["id"],
                label=label,
                city=city,
                country=country,
                latitude=latitude,
                longitude=longitude,
            )
        )
    return imported_nodes


def _parse_graphml_edges(
    root: ET.Element,
    key_map: dict[str, str],
    nodes_by_id: dict[str, ImportedNode],
) -> list[ImportedEdge]:
    graph = root.find("g:graph", GRAPHML_NAMESPACE)
    if graph is None:
        raise ValueError("GraphML file does not contain a <graph> element.")

    imported_edges: list[ImportedEdge] = []
    for edge_element in graph.findall("g:edge", GRAPHML_NAMESPACE):
        edge_data: dict[str, str] = {}
        for data_element in edge_element.findall("g:data", GRAPHML_NAMESPACE):
            key_id = data_element.attrib.get("key")
            key_name = key_map.get(key_id or "", key_id or "")
            text = (data_element.text or "").strip()
            if text:
                edge_data[key_name] = text

        source_id = edge_element.attrib["source"]
        target_id = edge_element.attrib["target"]
        source_node = nodes_by_id[source_id]
        target_node = nodes_by_id[target_id]
        imported_edges.append(
            ImportedEdge(
                source=source_id,
                target=target_id,
                bandwidth_mbps=_edge_bandwidth_mbps(edge_data),
                label=_edge_label(edge_data, source_node.label, target_node.label),
                raw_data=edge_data,
            )
        )
    return imported_edges


def _sorted_imported_edges(edges: list[ImportedEdge], nodes_by_id: dict[str, ImportedNode]) -> list[ImportedEdge]:
    return sorted(edges, key=lambda edge: (nodes_by_id[edge.source].label, nodes_by_id[edge.target].label))


def _scenario_targets(switch_names: list[str], links: list[dict[str, object]]) -> dict[str, object]:
    if not links:
        raise ValueError("Imported topology must contain at least one link.")

    first_link = [str(links[0]["src"]), str(links[0]["dst"])]
    second_link = [str(links[1]["src"]), str(links[1]["dst"])] if len(links) > 1 else first_link
    return {
        "single_link_failure": first_link,
        "recovery_scenario": first_link,
        "link_flap_scenario": first_link,
        "multi_fault_scenario": [first_link, second_link],
    }


def import_graphml_topology(graphml_path: Path, topology_name: str | None = None) -> dict[str, object]:
    """Convert a GraphML topology into the internal normalized topology JSON structure."""

    tree = ET.parse(graphml_path)
    root = tree.getroot()
    if _strip_namespace(root.tag) != "graphml":
        raise ValueError("Input file is not a GraphML document.")

    key_map = _graphml_key_map(root)
    imported_nodes = _parse_graphml_nodes(root, key_map)
    if not imported_nodes:
        raise ValueError("GraphML document does not contain any nodes.")

    nodes_by_id = {node.raw_id: node for node in imported_nodes}
    imported_edges = _sorted_imported_edges(_parse_graphml_edges(root, key_map, nodes_by_id), nodes_by_id)
    if not imported_edges:
        raise ValueError("GraphML document does not contain any edges.")

    sorted_nodes = sorted(imported_nodes, key=lambda node: node.label)
    node_name_map = {node.raw_id: f"s{index}" for index, node in enumerate(sorted_nodes, start=1)}

    switches: list[dict[str, object]] = []
    hosts: list[dict[str, object]] = []
    for index, node in enumerate(sorted_nodes, start=1):
        switch_name = node_name_map[node.raw_id]
        switches.append(
            {
                "name": switch_name,
                "dpid": normalize_dpid(index),
                "city": node.city,
                "country": node.country,
                "latitude": node.latitude,
                "longitude": node.longitude,
            }
        )
        hosts.append(
            {
                "name": f"h{index}",
                "switch": switch_name,
                "ip": f"10.0.0.{index}/24",
                "mac": f"00:00:00:00:00:{index:02x}",
            }
        )

    links: list[dict[str, object]] = []
    for edge in imported_edges:
        source_node = nodes_by_id[edge.source]
        target_node = nodes_by_id[edge.target]
        distance_km = _haversine_distance_km(
            source_node.latitude,
            source_node.longitude,
            target_node.latitude,
            target_node.longitude,
        )
        links.append(
            {
                "src": node_name_map[edge.source],
                "dst": node_name_map[edge.target],
                "bandwidth_mbps": edge.bandwidth_mbps,
                "delay_ms": _delay_from_distance(distance_km),
                "distance_km": round(distance_km, 3) if distance_km is not None else None,
                "label": edge.label,
                "source": "Imported GraphML topology",
                "enabled": True,
            }
        )

    output_name = topology_name or graphml_path.stem.lower().replace(" ", "_")
    return {
        "name": output_name,
        "description": f"Imported from GraphML source {graphml_path.name}.",
        "provenance": {
            "import_source": str(graphml_path),
            "import_format": "graphml",
            "importer": "src.topology.importers.graphml_importer",
        },
        "switches": switches,
        "hosts": hosts,
        "links": links,
        "scenario_targets": _scenario_targets([switch["name"] for switch in switches], links),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for the GraphML importer."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for GraphML import."""

    args = parse_args(argv)
    topology = import_graphml_topology(args.input, topology_name=args.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(topology, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
