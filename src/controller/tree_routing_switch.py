"""Topology-aware OpenFlow controller that routes known traffic on the spanning tree."""

from __future__ import annotations

from src.controller.topology_aware_switch import TopologyAwareSwitch


class TreeRoutingSwitch(TopologyAwareSwitch):
    """Conservative loop-safe controller that uses tree paths instead of full-graph shortest paths."""

    def _path_for_destination(self, src_switch: str, dst_switch: str) -> list[str] | None:
        return self.routing_state.spanning_tree_path(src_switch, dst_switch)
