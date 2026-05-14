"""Diff logic for identifying meaningful state changes between snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.twin.models import HostState, NetworkState, SwitchState


@dataclass(slots=True)
class StateChange:
    """Structured representation of one meaningful state change."""

    entity_type: str
    entity_id: str
    field_name: str
    old_value: Any
    new_value: Any
    details: dict[str, Any]


def diff_network_states(old_state: NetworkState | None, new_state: NetworkState) -> list[StateChange]:
    """Diff two snapshots and return meaningful changes for event generation."""

    if old_state is None:
        return []

    changes: list[StateChange] = []
    old_links = old_state.link_index()
    new_links = new_state.link_index()

    for link_id in sorted(set(old_links) | set(new_links)):
        old_link = old_links.get(link_id)
        new_link = new_links.get(link_id)
        old_is_up = old_link.is_up if old_link is not None else None
        new_is_up = new_link.is_up if new_link is not None else None

        if old_is_up == new_is_up:
            continue

        reference_link = new_link or old_link
        changes.append(
            StateChange(
                entity_type="link",
                entity_id=link_id,
                field_name="is_up",
                old_value=old_is_up,
                new_value=new_is_up,
                details={
                    "src_dpid": reference_link.src_dpid if reference_link else "",
                    "dst_dpid": reference_link.dst_dpid if reference_link else "",
                    "src_port": reference_link.src_port if reference_link else None,
                    "dst_port": reference_link.dst_port if reference_link else None,
                },
            )
        )

    old_switches = {switch.dpid: switch for switch in old_state.switches}
    new_switches = {switch.dpid: switch for switch in new_state.switches}

    for switch_id in sorted(set(old_switches) | set(new_switches)):
        old_switch = old_switches.get(switch_id)
        new_switch = new_switches.get(switch_id)
        old_present = old_switch is not None
        new_present = new_switch is not None
        if old_present != new_present:
            reference_switch = new_switch or old_switch
            changes.append(
                StateChange(
                    entity_type="switch",
                    entity_id=switch_id,
                    field_name="presence",
                    old_value=old_present,
                    new_value=new_present,
                    details={"name": reference_switch.name if reference_switch else switch_id},
                )
            )
            continue

        if old_switch is None or new_switch is None:
            continue
        baseline = max(old_switch.flow_count, 1)
        if abs(new_switch.flow_count - old_switch.flow_count) / baseline > 0.5:
            changes.append(
                StateChange(
                    entity_type="switch",
                    entity_id=switch_id,
                    field_name="flow_count",
                    old_value=old_switch.flow_count,
                    new_value=new_switch.flow_count,
                    details={"name": new_switch.name},
                )
            )

    old_hosts = {host.mac: host for host in old_state.hosts}
    new_hosts = {host.mac: host for host in new_state.hosts}

    for host_mac in sorted(set(old_hosts) | set(new_hosts)):
        old_host = old_hosts.get(host_mac)
        new_host = new_hosts.get(host_mac)
        old_present = old_host is not None
        new_present = new_host is not None
        if old_present != new_present:
            reference_host = new_host or old_host
            changes.append(
                StateChange(
                    entity_type="host",
                    entity_id=host_mac,
                    field_name="presence",
                    old_value=old_present,
                    new_value=new_present,
                    details={
                        "name": reference_host.name if reference_host else host_mac,
                        "attached_switch": reference_host.attached_switch if reference_host else None,
                        "attached_port": reference_host.attached_port if reference_host else None,
                    },
                )
            )
            continue

        if old_host is None or new_host is None:
            continue

        if old_host.attached_switch != new_host.attached_switch:
            changes.append(
                StateChange(
                    entity_type="host",
                    entity_id=host_mac,
                    field_name="attached_switch",
                    old_value=old_host.attached_switch,
                    new_value=new_host.attached_switch,
                    details={
                        "name": new_host.name,
                        "attached_port": new_host.attached_port,
                    },
                )
            )
        elif old_host.attached_port != new_host.attached_port:
            changes.append(
                StateChange(
                    entity_type="host",
                    entity_id=host_mac,
                    field_name="attached_port",
                    old_value=old_host.attached_port,
                    new_value=new_host.attached_port,
                    details={
                        "name": new_host.name,
                        "attached_switch": new_host.attached_switch,
                    },
                )
            )

    return changes
