"""Topology file loader for data-driven Mininet experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.controller.ryu_api_client import normalize_dpid


@dataclass(slots=True)
class TopologySwitchSpec:
    """Normalized switch definition loaded from a topology file."""

    name: str
    dpid: str
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(slots=True)
class TopologyHostSpec:
    """Normalized host definition loaded from a topology file."""

    name: str
    switch: str
    ip: str
    mac: str


@dataclass(slots=True)
class TopologyLinkSpec:
    """Normalized link definition loaded from a topology file."""

    src: str
    dst: str
    bandwidth_mbps: int = 100
    delay_ms: float = 10.0
    distance_km: float | None = None
    label: str | None = None
    source: str | None = None
    enabled: bool = True


@dataclass(slots=True)
class TopologyDefinition:
    """Full normalized topology definition."""

    name: str
    description: str
    switches: list[TopologySwitchSpec] = field(default_factory=list)
    hosts: list[TopologyHostSpec] = field(default_factory=list)
    links: list[TopologyLinkSpec] = field(default_factory=list)
    scenario_targets: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def switch_names(self) -> set[str]:
        return {switch.name for switch in self.switches}

    def switches_by_dpid(self) -> dict[str, TopologySwitchSpec]:
        return {switch.dpid: switch for switch in self.switches}

    def switches_by_name(self) -> dict[str, TopologySwitchSpec]:
        return {switch.name: switch for switch in self.switches}

    def link_metadata_by_dpid_pair(self) -> dict[frozenset[str], TopologyLinkSpec]:
        switches_by_name = self.switches_by_name()
        return {
            frozenset((switches_by_name[link.src].dpid, switches_by_name[link.dst].dpid)): link
            for link in self.active_links()
        }

    def link_for_switch_pair(self, src_switch: str, dst_switch: str) -> TopologyLinkSpec | None:
        for link in self.links:
            if frozenset((link.src, link.dst)) == frozenset((src_switch, dst_switch)):
                return link
        return None

    def active_links(self) -> list[TopologyLinkSpec]:
        return [link for link in self.links if link.enabled]


def _require_keys(payload: dict[str, Any], required_keys: set[str], context: str) -> None:
    missing = required_keys - payload.keys()
    if missing:
        keys = ", ".join(sorted(missing))
        raise ValueError(f"Missing required key(s) for {context}: {keys}")


def _optional_float(value: Any, field_name: str, context: str) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid float for {context} field {field_name!r}: {value!r}") from exc


def _validate_scenario_targets(definition: TopologyDefinition) -> None:
    switch_names = definition.switch_names()
    defined_links = {
        frozenset((link.src, link.dst))
        for link in definition.active_links()
    }

    for scenario_name, target in definition.scenario_targets.items():
        target_pairs = target if scenario_name == "multi_fault_scenario" else [target]
        if not isinstance(target_pairs, list):
            raise ValueError(f"Scenario target for {scenario_name!r} must be a list.")

        for pair in target_pairs:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError(f"Scenario target for {scenario_name!r} must be a two-switch pair.")
            src_switch, dst_switch = pair
            if src_switch not in switch_names or dst_switch not in switch_names:
                raise ValueError(f"Scenario target {pair!r} references an unknown switch.")
            if frozenset(pair) not in defined_links:
                raise ValueError(f"Scenario target {pair!r} does not match a defined topology link.")


def load_topology_definition(path: Path) -> TopologyDefinition:
    """Load and validate a normalized topology definition from JSON."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    _require_keys(payload, {"name", "switches", "hosts", "links"}, "topology root")

    switches: list[TopologySwitchSpec] = []
    seen_switch_names: set[str] = set()
    seen_dpids: set[str] = set()
    for item in payload["switches"]:
        _require_keys(item, {"name", "dpid"}, "switch")
        name = str(item["name"])
        dpid = normalize_dpid(item["dpid"])
        if name in seen_switch_names:
            raise ValueError(f"Duplicate switch name: {name}")
        if dpid in seen_dpids:
            raise ValueError(f"Duplicate switch dpid: {dpid}")
        seen_switch_names.add(name)
        seen_dpids.add(dpid)
        switches.append(
            TopologySwitchSpec(
                name=name,
                dpid=dpid,
                city=item.get("city"),
                country=item.get("country"),
                latitude=_optional_float(item.get("latitude"), "latitude", f"switch {name}"),
                longitude=_optional_float(item.get("longitude"), "longitude", f"switch {name}"),
            )
        )

    hosts: list[TopologyHostSpec] = []
    seen_host_names: set[str] = set()
    for item in payload["hosts"]:
        _require_keys(item, {"name", "switch", "ip", "mac"}, "host")
        host_name = str(item["name"])
        if host_name in seen_host_names:
            raise ValueError(f"Duplicate host name: {host_name}")
        if item["switch"] not in seen_switch_names:
            raise ValueError(f"Host {host_name!r} references an unknown switch: {item['switch']!r}")
        seen_host_names.add(host_name)
        hosts.append(
            TopologyHostSpec(
                name=host_name,
                switch=str(item["switch"]),
                ip=str(item["ip"]),
                mac=str(item["mac"]),
            )
        )

    links: list[TopologyLinkSpec] = []
    seen_links: set[frozenset[str]] = set()
    for item in payload["links"]:
        _require_keys(item, {"src", "dst"}, "link")
        src_switch = str(item["src"])
        dst_switch = str(item["dst"])
        if src_switch not in seen_switch_names or dst_switch not in seen_switch_names:
            raise ValueError(f"Link {src_switch!r}-{dst_switch!r} references an unknown switch.")
        link_key = frozenset((src_switch, dst_switch))
        if link_key in seen_links:
            raise ValueError(f"Duplicate undirected link: {src_switch}-{dst_switch}")
        seen_links.add(link_key)
        links.append(
            TopologyLinkSpec(
                src=src_switch,
                dst=dst_switch,
                bandwidth_mbps=int(item.get("bandwidth_mbps", 100)),
                delay_ms=float(item.get("delay_ms", 10)),
                distance_km=_optional_float(item.get("distance_km"), "distance_km", f"link {src_switch}-{dst_switch}"),
                label=item.get("label"),
                source=item.get("source"),
                enabled=bool(item.get("enabled", True)),
            )
        )

    definition = TopologyDefinition(
        name=str(payload["name"]),
        description=str(payload.get("description", "")),
        switches=switches,
        hosts=hosts,
        links=links,
        scenario_targets=dict(payload.get("scenario_targets", {})),
        provenance=dict(payload.get("provenance", {})),
    )
    _validate_scenario_targets(definition)
    return definition
