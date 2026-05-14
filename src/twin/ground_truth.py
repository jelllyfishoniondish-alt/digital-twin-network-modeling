"""Independent OVS/Mininet ground-truth collection for fidelity experiments."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from typing import Any

from src.controller.ryu_api_client import normalize_dpid
from src.topology.topology_loader import TopologyDefinition
from src.twin.models import LinkState, NetworkState, PortState, SwitchState, utc_now_iso


_PORT_DESC_HEADER_RE = re.compile(r"^\s*(\d+)\(([^)]+)\):")
_PORT_STATE_RE = re.compile(r"^\s*state:\s*(.+)$")
_RX_COUNTER_RE = re.compile(r"rx pkts=(\d+), bytes=(\d+)")
_TX_COUNTER_RE = re.compile(r"tx pkts=(\d+), bytes=(\d+)")


@dataclass(slots=True)
class OvsPortTruth:
    """Independent OVS dataplane view for one switch interface."""

    interface_name: str
    port_no: int
    is_up: bool = True
    rx_packets: int = 0
    tx_packets: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0


def parse_ovs_ofctl_dump_ports_desc(output: str) -> dict[str, OvsPortTruth]:
    """Parse `ovs-ofctl dump-ports-desc` output into interface states."""

    ports: dict[str, OvsPortTruth] = {}
    current: OvsPortTruth | None = None
    for raw_line in output.splitlines():
        header_match = _PORT_DESC_HEADER_RE.match(raw_line)
        if header_match is not None:
            current = OvsPortTruth(
                interface_name=header_match.group(2),
                port_no=int(header_match.group(1)),
                is_up=True,
            )
            ports[current.interface_name] = current
            continue

        if current is None:
            continue

        state_match = _PORT_STATE_RE.match(raw_line)
        if state_match is None:
            continue

        state_payload = state_match.group(1).strip().upper()
        if state_payload in {"0", "[]", ""}:
            current.is_up = True
        elif "LINK_DOWN" in state_payload:
            current.is_up = False
    return ports


def parse_ovs_ofctl_dump_ports(output: str) -> dict[str, int]:
    """Parse `ovs-ofctl dump-ports` output into packet/byte counters."""

    counters = {
        "rx_packets": 0,
        "tx_packets": 0,
        "rx_bytes": 0,
        "tx_bytes": 0,
    }
    for raw_line in output.splitlines():
        rx_match = _RX_COUNTER_RE.search(raw_line)
        if rx_match is not None:
            counters["rx_packets"] = int(rx_match.group(1))
            counters["rx_bytes"] = int(rx_match.group(2))
            continue

        tx_match = _TX_COUNTER_RE.search(raw_line)
        if tx_match is not None:
            counters["tx_packets"] = int(tx_match.group(1))
            counters["tx_bytes"] = int(tx_match.group(2))
    return counters


def _network_switches(network, topology_definition: TopologyDefinition | None) -> list[object]:
    runtime_switches = {switch.name: switch for switch in getattr(network, "switches", [])}
    if topology_definition is not None:
        ordered_switches: list[object] = []
        for switch in topology_definition.switches:
            if switch.name in runtime_switches:
                ordered_switches.append(runtime_switches[switch.name])
        if ordered_switches:
            return ordered_switches
    return sorted(runtime_switches.values(), key=lambda switch: switch.name)


def _lookup_runtime_switch(network, switch_name: str):
    if hasattr(network, "get"):
        return network.get(switch_name)
    for switch in getattr(network, "switches", []):
        if switch.name == switch_name:
            return switch
    raise ValueError(f"Switch {switch_name!r} not found in network.")


def _switch_dpid(runtime_switch, topology_definition: TopologyDefinition | None) -> str:
    if topology_definition is not None:
        metadata = topology_definition.switches_by_name().get(runtime_switch.name)
        if metadata is not None:
            return metadata.dpid
    raw_dpid = getattr(runtime_switch, "dpid", runtime_switch.name)
    return normalize_dpid(raw_dpid)


def _collect_switch_port_truth(runtime_switch) -> dict[str, OvsPortTruth]:
    desc_output = runtime_switch.cmd(f"ovs-ofctl dump-ports-desc {runtime_switch.name}")
    ports = parse_ovs_ofctl_dump_ports_desc(desc_output)
    for port_truth in ports.values():
        counters_output = runtime_switch.cmd(
            f"ovs-ofctl dump-ports {runtime_switch.name} {port_truth.port_no}"
        )
        counters = parse_ovs_ofctl_dump_ports(counters_output)
        port_truth.rx_packets = counters["rx_packets"]
        port_truth.tx_packets = counters["tx_packets"]
        port_truth.rx_bytes = counters["rx_bytes"]
        port_truth.tx_bytes = counters["tx_bytes"]
    return ports


def _switch_states(
    network,
    topology_definition: TopologyDefinition | None,
) -> tuple[list[SwitchState], dict[str, dict[str, OvsPortTruth]], dict[str, str]]:
    switch_states: list[SwitchState] = []
    port_truth_by_switch: dict[str, dict[str, OvsPortTruth]] = {}
    dpid_by_switch_name: dict[str, str] = {}
    topology_switches = topology_definition.switches_by_name() if topology_definition is not None else {}

    for runtime_switch in _network_switches(network, topology_definition):
        port_truth = _collect_switch_port_truth(runtime_switch)
        dpid = _switch_dpid(runtime_switch, topology_definition)
        dpid_by_switch_name[runtime_switch.name] = dpid
        port_truth_by_switch[runtime_switch.name] = port_truth
        switch_metadata = topology_switches.get(runtime_switch.name)
        switch_states.append(
            SwitchState(
                dpid=dpid,
                name=runtime_switch.name,
                city=switch_metadata.city if switch_metadata is not None else None,
                country=switch_metadata.country if switch_metadata is not None else None,
                latitude=switch_metadata.latitude if switch_metadata is not None else None,
                longitude=switch_metadata.longitude if switch_metadata is not None else None,
                ports=[
                    PortState(
                        port_no=truth.port_no,
                        rx_packets=truth.rx_packets,
                        tx_packets=truth.tx_packets,
                        rx_bytes=truth.rx_bytes,
                        tx_bytes=truth.tx_bytes,
                        is_up=truth.is_up,
                    )
                    for truth in sorted(port_truth.values(), key=lambda item: item.port_no)
                ],
                flow_count=0,
            )
        )
    return switch_states, port_truth_by_switch, dpid_by_switch_name


def _topology_links(network, topology_definition: TopologyDefinition | None):
    if topology_definition is not None:
        for link in topology_definition.active_links():
            yield link.src, link.dst, link
        return

    switch_names = [switch.name for switch in _network_switches(network, topology_definition=None)]
    for src_switch, dst_switch in combinations(sorted(switch_names), 2):
        yield src_switch, dst_switch, None


def build_ovs_ground_truth_state(
    network,
    topology_definition: TopologyDefinition | None = None,
    *,
    timestamp: str | None = None,
) -> NetworkState:
    """Build a `NetworkState` from OVS dataplane state instead of Ryu REST."""

    switches, port_truth_by_switch, dpid_by_switch_name = _switch_states(network, topology_definition)
    links: list[LinkState] = []
    for src_switch_name, dst_switch_name, link_metadata in _topology_links(network, topology_definition):
        src_switch = _lookup_runtime_switch(network, src_switch_name)
        dst_switch = _lookup_runtime_switch(network, dst_switch_name)
        for src_intf, dst_intf in src_switch.connectionsTo(dst_switch):
            src_port_truth = port_truth_by_switch.get(src_switch_name, {}).get(src_intf.name)
            dst_port_truth = port_truth_by_switch.get(dst_switch_name, {}).get(dst_intf.name)
            if src_port_truth is None or dst_port_truth is None:
                continue
            links.append(
                LinkState(
                    src_dpid=dpid_by_switch_name[src_switch_name],
                    dst_dpid=dpid_by_switch_name[dst_switch_name],
                    src_port=src_port_truth.port_no,
                    dst_port=dst_port_truth.port_no,
                    is_up=src_port_truth.is_up and dst_port_truth.is_up,
                    latency_ms=link_metadata.delay_ms if link_metadata is not None else 0.0,
                    label=link_metadata.label if link_metadata is not None else None,
                    distance_km=link_metadata.distance_km if link_metadata is not None else None,
                    bandwidth_mbps=link_metadata.bandwidth_mbps if link_metadata is not None else None,
                )
            )

    return NetworkState(
        timestamp=timestamp or utc_now_iso(),
        switches=switches,
        links=links,
        hosts=[],
    )


def wait_for_ovs_link_state(
    network,
    src_switch: str,
    dst_switch: str,
    expected_up: bool,
    *,
    topology_definition: TopologyDefinition | None = None,
    timeout_seconds: float = 5.0,
    sleep_seconds: float = 0.05,
) -> str | None:
    """Wait until OVS reports the target switch-to-switch link in the expected state."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            observed_at = datetime.now().astimezone().isoformat()
            truth_state = build_ovs_ground_truth_state(
                network,
                topology_definition=topology_definition,
                timestamp=observed_at,
            )
            expected_dpids = {
                _switch_dpid(_lookup_runtime_switch(network, src_switch), topology_definition),
                _switch_dpid(_lookup_runtime_switch(network, dst_switch), topology_definition),
            }
            for link in truth_state.links:
                if {link.src_dpid, link.dst_dpid} == expected_dpids and link.is_up == expected_up:
                    return observed_at
        except Exception:
            return None
        time.sleep(sleep_seconds)
    return None
