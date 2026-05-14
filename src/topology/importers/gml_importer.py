"""Import Topology Zoo style GML files into the internal topology JSON format."""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from src.controller.ryu_api_client import normalize_dpid


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


def _tokenize_gml(text: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "[]":
            tokens.append(char)
            index += 1
            continue
        if char == '"':
            index += 1
            start = index
            while index < len(text) and text[index] != '"':
                if text[index] == "\\" and index + 1 < len(text):
                    index += 2
                    continue
                index += 1
            tokens.append(text[start:index].replace('\\"', '"'))
            index += 1
            continue
        start = index
        while index < len(text) and not text[index].isspace() and text[index] not in '[]"':
            index += 1
        tokens.append(text[start:index])
    return tokens


def _parse_scalar(value: str) -> str | float | int:
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _parse_gml_tokens(tokens: list[str], index: int = 0) -> tuple[dict[str, object], int]:
    parsed: dict[str, object] = {}
    while index < len(tokens):
        token = tokens[index]
        if token == "]":
            return parsed, index + 1
        key = token
        index += 1
        if index >= len(tokens):
            raise ValueError(f"Unexpected end of GML after key {key!r}.")
        value_token = tokens[index]
        if value_token == "[":
            nested, index = _parse_gml_tokens(tokens, index + 1)
            existing = parsed.get(key)
            if existing is None:
                parsed[key] = [nested]
            elif isinstance(existing, list):
                existing.append(nested)
            else:
                parsed[key] = [existing, nested]
        else:
            parsed[key] = _parse_scalar(value_token)
            index += 1
    return parsed, index


def _safe_float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _canonical_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _node_coordinates(payload: dict[str, object]) -> tuple[float | None, float | None]:
    latitude = None
    longitude = None
    for key, value in payload.items():
        canonical = _canonical_name(str(key))
        if canonical in {"latitude", "lat"}:
            latitude = _safe_float(value)
        elif canonical in {"longitude", "lon", "lng"}:
            longitude = _safe_float(value)
    return latitude, longitude


def _node_city_country(label: str, payload: dict[str, object]) -> tuple[str | None, str | None]:
    city = payload.get("City") or payload.get("city")
    country = payload.get("Country") or payload.get("country")
    if city is not None:
        return str(city), str(country) if country is not None else None
    if country is not None and re.fullmatch(r"[A-Z]{2,3}", label):
        return str(country), str(country)
    if "," in label:
        city_part, country_part = [part.strip() for part in label.split(",", 1)]
        return city_part or None, str(country) if country is not None else country_part or None
    return label or None, str(country) if country is not None else None


def _edge_bandwidth_mbps(payload: dict[str, object]) -> int:
    for key in ("LinkSpeedRaw", "capacity", "Capacity", "LinkSpeed", "LinkLabel"):
        numeric = _safe_float(payload.get(key))
        if numeric is None or numeric <= 0:
            continue
        if numeric > 1_000_000:
            return max(1, int(numeric / 1_000_000))
        if numeric > 10_000:
            return max(1, int(numeric / 1_000))
        return max(1, int(numeric))
    return 100


def _edge_label(payload: dict[str, object], source_label: str, target_label: str) -> str:
    for key in ("label", "Label", "LinkLabel"):
        if payload.get(key):
            return str(payload[key])
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


def _scenario_targets(links: list[dict[str, object]]) -> dict[str, object]:
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


def import_gml_topology(gml_path: Path, topology_name: str | None = None) -> dict[str, object]:
    """Convert a GML topology into the internal normalized topology JSON structure."""

    tokens = _tokenize_gml(gml_path.read_text(encoding="utf-8"))
    parsed, _ = _parse_gml_tokens(tokens)
    graph_entries = parsed.get("graph")
    if not isinstance(graph_entries, list) or not graph_entries:
        raise ValueError("GML file does not contain a graph definition.")
    graph = graph_entries[0]
    if not isinstance(graph, dict):
        raise ValueError("GML graph payload is malformed.")

    raw_nodes = graph.get("node", [])
    raw_edges = graph.get("edge", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise ValueError("GML graph nodes or edges are malformed.")

    imported_nodes: list[ImportedNode] = []
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            continue
        label = str(raw_node.get("label", raw_node.get("id")))
        city, country = _node_city_country(label, raw_node)
        latitude, longitude = _node_coordinates(raw_node)
        imported_nodes.append(
            ImportedNode(
                raw_id=str(raw_node.get("id")),
                label=label,
                city=city,
                country=country,
                latitude=latitude,
                longitude=longitude,
            )
        )
    if not imported_nodes:
        raise ValueError("GML document does not contain any nodes.")

    nodes_by_id = {node.raw_id: node for node in imported_nodes}
    sorted_nodes = sorted(imported_nodes, key=lambda node: node.label)
    node_name_map = {node.raw_id: f"s{index}" for index, node in enumerate(sorted_nodes, start=1)}

    imported_edges: list[ImportedEdge] = []
    for raw_edge in raw_edges:
        if not isinstance(raw_edge, dict):
            continue
        source_id = str(raw_edge.get("source"))
        target_id = str(raw_edge.get("target"))
        source_node = nodes_by_id[source_id]
        target_node = nodes_by_id[target_id]
        imported_edges.append(
            ImportedEdge(
                source=source_id,
                target=target_id,
                bandwidth_mbps=_edge_bandwidth_mbps(raw_edge),
                label=_edge_label(raw_edge, source_node.label, target_node.label),
            )
        )
    imported_edges = sorted(imported_edges, key=lambda edge: (nodes_by_id[edge.source].label, nodes_by_id[edge.target].label))
    if not imported_edges:
        raise ValueError("GML document does not contain any edges.")

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
                "source": "Imported GML topology",
                "enabled": True,
            }
        )

    output_name = topology_name or gml_path.stem.lower().replace(" ", "_")
    return {
        "name": output_name,
        "description": f"Imported from GML source {gml_path.name}.",
        "provenance": {
            "import_source": str(gml_path),
            "import_format": "gml",
            "importer": "src.topology.importers.gml_importer",
        },
        "switches": switches,
        "hosts": hosts,
        "links": links,
        "scenario_targets": _scenario_targets(links),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for the GML importer."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for GML import."""

    args = parse_args(argv)
    topology = import_gml_topology(args.input, topology_name=args.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(topology, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
