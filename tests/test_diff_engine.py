"""Tests for the state diff engine."""

from src.twin.diff_engine import diff_network_states
from src.twin.models import LinkState, NetworkState


def test_diff_network_states_detects_link_down() -> None:
    old_state = NetworkState(
        timestamp="2026-04-01T12:00:00+00:00",
        links=[
            LinkState(
                src_dpid="0000000000000001",
                dst_dpid="0000000000000002",
                src_port=2,
                dst_port=1,
                is_up=True,
            )
        ],
    )
    new_state = NetworkState(
        timestamp="2026-04-01T12:00:02+00:00",
        links=[
            LinkState(
                src_dpid="0000000000000001",
                dst_dpid="0000000000000002",
                src_port=2,
                dst_port=1,
                is_up=False,
            )
        ],
    )

    changes = diff_network_states(old_state, new_state)

    assert len(changes) == 1
    assert changes[0].entity_type == "link"
    assert changes[0].old_value is True
    assert changes[0].new_value is False
