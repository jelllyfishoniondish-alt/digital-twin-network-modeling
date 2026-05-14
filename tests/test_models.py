"""Tests for the core state models."""

from src.twin.models import HostState, LinkState, NetworkState, PortState, SwitchState


def test_network_state_serialization() -> None:
    state = NetworkState(
        timestamp="2026-04-01T12:00:00+00:00",
        switches=[
            SwitchState(
                dpid="0000000000000001",
                name="s1",
                ports=[PortState(port_no=1, rx_packets=1, tx_packets=2)],
                flow_count=3,
            )
        ],
        links=[
            LinkState(
                src_dpid="0000000000000001",
                dst_dpid="0000000000000002",
                src_port=2,
                dst_port=1,
                is_up=True,
                latency_ms=10.0,
            )
        ],
        hosts=[
            HostState(
                name="h1",
                ip="10.0.0.1/24",
                mac="00:00:00:00:00:01",
                attached_switch="0000000000000001",
                attached_port=1,
            )
        ],
    )

    payload = state.to_dict()
    assert payload["timestamp"] == "2026-04-01T12:00:00+00:00"
    assert payload["switches"][0]["flow_count"] == 3
    assert payload["links"][0]["link_id"] == "0000000000000001:2--0000000000000002:1"
    assert payload["hosts"][0]["name"] == "h1"
