"""Extended diff tests for switch and host changes."""

from src.twin.diff_engine import diff_network_states
from src.twin.models import HostState, NetworkState, SwitchState


def test_diff_network_states_detects_switch_presence_and_flow_count_changes() -> None:
    old_state = NetworkState(
        timestamp="2026-04-01T12:00:00+00:00",
        switches=[
            SwitchState(dpid="1", name="s1", flow_count=10),
            SwitchState(dpid="2", name="s2", flow_count=10),
        ],
    )
    new_state = NetworkState(
        timestamp="2026-04-01T12:00:02+00:00",
        switches=[
            SwitchState(dpid="1", name="s1", flow_count=20),
            SwitchState(dpid="3", name="s3", flow_count=1),
        ],
    )

    changes = diff_network_states(old_state, new_state)

    assert ("switch", "1", "flow_count", 10, 20) in {
        (change.entity_type, change.entity_id, change.field_name, change.old_value, change.new_value)
        for change in changes
    }
    assert ("switch", "2", "presence", True, False) in {
        (change.entity_type, change.entity_id, change.field_name, change.old_value, change.new_value)
        for change in changes
    }
    assert ("switch", "3", "presence", False, True) in {
        (change.entity_type, change.entity_id, change.field_name, change.old_value, change.new_value)
        for change in changes
    }


def test_diff_network_states_detects_host_join_leave_and_migrate() -> None:
    old_state = NetworkState(
        timestamp="2026-04-01T12:00:00+00:00",
        hosts=[
            HostState(name="h1", ip="10.0.0.1", mac="00:00:00:00:00:01", attached_switch="1", attached_port=1),
            HostState(name="h2", ip="10.0.0.2", mac="00:00:00:00:00:02", attached_switch="1", attached_port=2),
        ],
    )
    new_state = NetworkState(
        timestamp="2026-04-01T12:00:02+00:00",
        hosts=[
            HostState(name="h1", ip="10.0.0.1", mac="00:00:00:00:00:01", attached_switch="2", attached_port=4),
            HostState(name="h3", ip="10.0.0.3", mac="00:00:00:00:00:03", attached_switch="3", attached_port=1),
        ],
    )

    changes = diff_network_states(old_state, new_state)
    tuples = {
        (change.entity_type, change.entity_id, change.field_name, change.old_value, change.new_value)
        for change in changes
    }

    assert ("host", "00:00:00:00:00:01", "attached_switch", "1", "2") in tuples
    assert ("host", "00:00:00:00:00:02", "presence", True, False) in tuples
    assert ("host", "00:00:00:00:00:03", "presence", False, True) in tuples
