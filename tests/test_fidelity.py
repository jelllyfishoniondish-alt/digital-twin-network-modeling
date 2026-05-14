"""Tests for fidelity metric calculations."""

from __future__ import annotations

from src.twin.fidelity import (
    compute_fidelity_report,
    compute_link_state_accuracy,
    compute_port_counter_drift,
    compute_topology_accuracy,
)
from src.twin.models import LinkState, NetworkState, PortState, SwitchState


def _state(
    *,
    switches: list[SwitchState] | None = None,
    links: list[LinkState] | None = None,
    timestamp: str = "2026-04-01T12:00:00+00:00",
) -> NetworkState:
    return NetworkState(
        timestamp=timestamp,
        switches=switches or [],
        links=links or [],
        hosts=[],
    )


def test_compute_topology_accuracy_uses_jaccard_similarity() -> None:
    twin = _state(
        switches=[SwitchState(dpid="1", name="s1"), SwitchState(dpid="2", name="s2")],
        links=[LinkState("1", "2", 1, 1)],
    )
    truth = _state(
        switches=[SwitchState(dpid="1", name="s1"), SwitchState(dpid="3", name="s3")],
        links=[LinkState("1", "3", 1, 1)],
    )

    assert compute_topology_accuracy(twin, truth) == 0.2


def test_compute_link_state_accuracy_penalizes_missing_or_mismatched_links() -> None:
    twin = _state(links=[LinkState("1", "2", 1, 1, is_up=True), LinkState("2", "3", 1, 1, is_up=False)])
    truth = _state(links=[LinkState("1", "2", 1, 1, is_up=True), LinkState("2", "3", 1, 1, is_up=True)])

    assert compute_link_state_accuracy(twin, truth) == 0.5


def test_compute_port_counter_drift_uses_total_bytes_per_port() -> None:
    twin = _state(
        switches=[
            SwitchState(
                dpid="1",
                name="s1",
                ports=[PortState(port_no=1, rx_bytes=120, tx_bytes=80)],
            )
        ]
    )
    truth = _state(
        switches=[
            SwitchState(
                dpid="1",
                name="s1",
                ports=[PortState(port_no=1, rx_bytes=100, tx_bytes=100)],
            )
        ]
    )

    assert compute_port_counter_drift(twin, truth) == {"1:1": 0.0}


def test_compute_fidelity_report_handles_empty_states() -> None:
    twin = _state()
    truth = _state()

    report = compute_fidelity_report(twin, truth)

    assert report.topology_accuracy == 1.0
    assert report.link_state_accuracy == 1.0
    assert report.port_counter_drift == {}
    assert 0.0 <= report.overall_fidelity <= 1.0
