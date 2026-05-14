"""Tests for the pure topology-routing helpers used by the Ryu controller."""

from src.controller.topology_routing import LinkAttachment, TopologyRoutingState


def _build_looped_state() -> TopologyRoutingState:
    state = TopologyRoutingState()
    state.replace_links(
        [
            LinkAttachment(src_switch="1", src_port=2, dst_switch="2", dst_port=2),
            LinkAttachment(src_switch="1", src_port=3, dst_switch="3", dst_port=2),
            LinkAttachment(src_switch="2", src_port=3, dst_switch="3", dst_port=3),
            LinkAttachment(src_switch="2", src_port=4, dst_switch="4", dst_port=2),
        ]
    )
    state.replace_switch_ports(
        {
            "1": {1, 2, 3},
            "2": {1, 2, 3, 4},
            "3": {1, 2, 3},
            "4": {1, 2},
        }
    )
    return state


def test_shortest_path_prefers_deterministic_bfs_order() -> None:
    state = _build_looped_state()

    path = state.shortest_path("1", "4")

    assert path == ["1", "2", "4"]


def test_output_port_for_path_uses_next_hop_and_host_attachment() -> None:
    state = _build_looped_state()
    state.learn_host("00:00:00:00:00:aa", switch_id="4", port_no=1)

    assert state.output_port_for_path(["1", "2", "4"], current_switch="1", dst_mac="00:00:00:00:00:aa") == 2
    assert state.output_port_for_path(["4"], current_switch="4", dst_mac="00:00:00:00:00:aa") == 1


def test_spanning_tree_path_uses_tree_route_instead_of_shortest_cross_link() -> None:
    state = _build_looped_state()

    path = state.spanning_tree_path("3", "4", root_switch="1")

    assert path == ["3", "1", "2", "4"]


def test_flood_ports_use_spanning_tree_and_host_ports_only() -> None:
    state = _build_looped_state()

    flood_ports = state.flood_ports("2", in_port=2, root_switch="1")

    assert flood_ports == [1, 4]


def test_host_learning_rejects_inter_switch_ports() -> None:
    state = _build_looped_state()

    assert state.is_host_facing_port("2", 1) is True
    assert state.is_host_facing_port("2", 2) is False
