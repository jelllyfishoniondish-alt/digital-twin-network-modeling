"""Pure routing helpers for the topology-aware Ryu controller."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass(slots=True)
class HostAttachment:
    """Attachment point for one learned host."""

    switch_id: str
    port_no: int


@dataclass(slots=True)
class LinkAttachment:
    """Attachment point for one switch-to-switch link endpoint."""

    src_switch: str
    src_port: int
    dst_switch: str
    dst_port: int


@dataclass(slots=True)
class TopologyRoutingState:
    """Topology graph and learned host locations used by the controller."""

    adjacency: dict[str, dict[str, int]] = field(default_factory=dict)
    switch_ports: dict[str, set[int]] = field(default_factory=dict)
    host_locations: dict[str, HostAttachment] = field(default_factory=dict)
    host_ports_by_switch: dict[str, set[int]] = field(default_factory=dict)

    def inter_switch_ports(self, switch_id: str) -> set[int]:
        """Return ports currently used for switch-to-switch links."""

        return set(self.adjacency.get(switch_id, {}).values())

    def is_host_facing_port(self, switch_id: str, port_no: int) -> bool:
        """Return whether a port is considered host-facing in the current topology."""

        if port_no in self.inter_switch_ports(switch_id):
            return False
        known_ports = self.switch_ports.get(switch_id)
        if known_ports is None:
            return True
        return port_no in known_ports

    def replace_links(self, links: list[LinkAttachment]) -> None:
        """Replace the current graph with a new link set."""

        adjacency: dict[str, dict[str, int]] = {}
        for link in links:
            adjacency.setdefault(link.src_switch, {})[link.dst_switch] = link.src_port
            adjacency.setdefault(link.dst_switch, {})[link.src_switch] = link.dst_port
        self.adjacency = adjacency

    def replace_switch_ports(self, switch_ports: dict[str, set[int]]) -> None:
        """Replace the known switch port inventory."""

        self.switch_ports = {switch_id: set(ports) for switch_id, ports in switch_ports.items()}

    def learn_host(self, mac_address: str, switch_id: str, port_no: int) -> None:
        """Learn or update a host attachment point."""

        previous = self.host_locations.get(mac_address)
        if previous is not None:
            previous_ports = self.host_ports_by_switch.get(previous.switch_id, set())
            previous_ports.discard(previous.port_no)
            if not previous_ports and previous.switch_id in self.host_ports_by_switch:
                del self.host_ports_by_switch[previous.switch_id]

        self.host_locations[mac_address] = HostAttachment(switch_id=switch_id, port_no=port_no)
        self.host_ports_by_switch.setdefault(switch_id, set()).add(port_no)

    def shortest_path(self, src_switch: str, dst_switch: str) -> list[str] | None:
        """Return the shortest path between two switches as a list of switch IDs."""

        if src_switch == dst_switch:
            return [src_switch]
        if src_switch not in self.adjacency or dst_switch not in self.adjacency:
            return None

        queue: deque[str] = deque([src_switch])
        previous: dict[str, str | None] = {src_switch: None}

        while queue:
            current = queue.popleft()
            for neighbor in sorted(self.adjacency.get(current, {})):
                if neighbor in previous:
                    continue
                previous[neighbor] = current
                if neighbor == dst_switch:
                    queue.clear()
                    break
                queue.append(neighbor)

        if dst_switch not in previous:
            return None

        path = [dst_switch]
        while previous[path[-1]] is not None:
            path.append(previous[path[-1]])  # type: ignore[arg-type]
        path.reverse()
        return path

    def spanning_tree_path(self, src_switch: str, dst_switch: str, root_switch: str | None = None) -> list[str] | None:
        """Return the path between two switches constrained to the deterministic spanning tree."""

        if src_switch == dst_switch:
            return [src_switch]

        tree_ports = self.spanning_tree_ports(root_switch=root_switch)
        if not tree_ports:
            return None

        tree_adjacency: dict[str, set[str]] = {switch_id: set() for switch_id in self.adjacency}
        for switch_id, neighbors in self.adjacency.items():
            for neighbor, port_no in neighbors.items():
                if port_no in tree_ports.get(switch_id, set()):
                    tree_adjacency.setdefault(switch_id, set()).add(neighbor)

        if src_switch not in tree_adjacency or dst_switch not in tree_adjacency:
            return None

        queue: deque[str] = deque([src_switch])
        previous: dict[str, str | None] = {src_switch: None}

        while queue:
            current = queue.popleft()
            for neighbor in sorted(tree_adjacency.get(current, set())):
                if neighbor in previous:
                    continue
                previous[neighbor] = current
                if neighbor == dst_switch:
                    queue.clear()
                    break
                queue.append(neighbor)

        if dst_switch not in previous:
            return None

        path = [dst_switch]
        while previous[path[-1]] is not None:
            path.append(previous[path[-1]])  # type: ignore[arg-type]
        path.reverse()
        return path

    def output_port_for_path(self, path: list[str], current_switch: str, dst_mac: str) -> int | None:
        """Return the egress port for a path step or final host attachment."""

        if not path:
            return None
        if len(path) == 1:
            attachment = self.host_locations.get(dst_mac)
            if attachment is None or attachment.switch_id != current_switch:
                return None
            return attachment.port_no

        for index, switch_id in enumerate(path[:-1]):
            if switch_id != current_switch:
                continue
            next_hop = path[index + 1]
            return self.adjacency.get(current_switch, {}).get(next_hop)
        return None

    def spanning_tree_ports(self, root_switch: str | None = None) -> dict[str, set[int]]:
        """Build a deterministic spanning tree and return its switch-to-switch ports."""

        if not self.adjacency:
            return {}

        root = root_switch or sorted(self.adjacency)[0]
        queue: deque[str] = deque([root])
        visited = {root}
        tree_ports: dict[str, set[int]] = {switch_id: set() for switch_id in self.adjacency}

        while queue:
            current = queue.popleft()
            for neighbor in sorted(self.adjacency.get(current, {})):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
                tree_ports[current].add(self.adjacency[current][neighbor])
                tree_ports.setdefault(neighbor, set()).add(self.adjacency[neighbor][current])

        return tree_ports

    def flood_ports(self, switch_id: str, in_port: int, root_switch: str | None = None) -> list[int]:
        """Return loop-safe flooding ports using a spanning tree plus host-facing ports."""

        tree_ports = self.spanning_tree_ports(root_switch=root_switch)
        candidate_ports = set(tree_ports.get(switch_id, set()))
        inter_switch_ports = self.inter_switch_ports(switch_id)
        candidate_ports.update(self.switch_ports.get(switch_id, set()) - inter_switch_ports)
        candidate_ports.update(self.host_ports_by_switch.get(switch_id, set()))
        candidate_ports.discard(in_port)
        return sorted(candidate_ports)
