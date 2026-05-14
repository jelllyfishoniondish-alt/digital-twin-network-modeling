"""Fidelity metrics comparing twin state against live controller ground truth."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from src.twin.models import NetworkState, utc_now_iso


@dataclass(slots=True)
class FidelityReport:
    """Quantitative fidelity summary for one twin-vs-truth comparison."""

    timestamp: str
    topology_accuracy: float
    link_state_accuracy: float
    port_counter_drift: dict[str, float]
    state_staleness_ms: float
    overall_fidelity: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _timestamp_diff_ms(timestamp: str) -> float:
    return max(
        0.0,
        (datetime.now(timezone.utc) - datetime.fromisoformat(timestamp)).total_seconds() * 1000,
    )


def compute_topology_accuracy(twin_state: NetworkState, ground_truth_state: NetworkState) -> float:
    """Compute Jaccard similarity across switch and link identities."""

    twin_entities = {f"switch:{switch.dpid}" for switch in twin_state.switches}
    twin_entities.update(f"link:{link.key()}" for link in twin_state.links)

    truth_entities = {f"switch:{switch.dpid}" for switch in ground_truth_state.switches}
    truth_entities.update(f"link:{link.key()}" for link in ground_truth_state.links)

    union = twin_entities | truth_entities
    if not union:
        return 1.0
    return len(twin_entities & truth_entities) / len(union)


def compute_link_state_accuracy(twin_state: NetworkState, ground_truth_state: NetworkState) -> float:
    """Compute the ratio of links whose up/down state matches ground truth."""

    twin_links = twin_state.link_index()
    truth_links = ground_truth_state.link_index()
    all_link_ids = set(twin_links) | set(truth_links)
    if not all_link_ids:
        return 1.0

    matches = 0
    for link_id in all_link_ids:
        twin_is_up = twin_links.get(link_id).is_up if link_id in twin_links else None
        truth_is_up = truth_links.get(link_id).is_up if link_id in truth_links else None
        if twin_is_up == truth_is_up:
            matches += 1
    return matches / len(all_link_ids)


def compute_port_counter_drift(twin_state: NetworkState, ground_truth_state: NetworkState) -> dict[str, float]:
    """Compute per-port byte-counter drift as a percentage against ground truth."""

    twin_ports = {
        f"{switch.dpid}:{port.port_no}": port
        for switch in twin_state.switches
        for port in switch.ports
    }
    truth_ports = {
        f"{switch.dpid}:{port.port_no}": port
        for switch in ground_truth_state.switches
        for port in switch.ports
    }

    drift: dict[str, float] = {}
    for port_id in sorted(set(twin_ports) | set(truth_ports)):
        twin_total = 0
        truth_total = 0
        if port_id in twin_ports:
            twin_port = twin_ports[port_id]
            twin_total = twin_port.rx_bytes + twin_port.tx_bytes
        if port_id in truth_ports:
            truth_port = truth_ports[port_id]
            truth_total = truth_port.rx_bytes + truth_port.tx_bytes
        drift[port_id] = abs(twin_total - truth_total) / max(truth_total, 1)
    return drift


def compute_fidelity_report(twin_state: NetworkState, ground_truth_state: NetworkState) -> FidelityReport:
    """Build a composite fidelity report from the current twin and ground truth states."""

    topology_accuracy = compute_topology_accuracy(twin_state, ground_truth_state)
    link_state_accuracy = compute_link_state_accuracy(twin_state, ground_truth_state)
    port_counter_drift = compute_port_counter_drift(twin_state, ground_truth_state)
    average_drift = sum(port_counter_drift.values()) / len(port_counter_drift) if port_counter_drift else 0.0
    counter_score = _clamp_unit(1.0 - average_drift)
    overall_fidelity = _clamp_unit(
        topology_accuracy * 0.3 + link_state_accuracy * 0.5 + counter_score * 0.2
    )

    return FidelityReport(
        timestamp=utc_now_iso(),
        topology_accuracy=topology_accuracy,
        link_state_accuracy=link_state_accuracy,
        port_counter_drift=port_counter_drift,
        state_staleness_ms=_timestamp_diff_ms(twin_state.timestamp),
        overall_fidelity=overall_fidelity,
    )
