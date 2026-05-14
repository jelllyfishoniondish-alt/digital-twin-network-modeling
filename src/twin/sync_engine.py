"""Polling-based sync engine that builds `NetworkState` from Ryu REST data."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.controller.ryu_api_client import RyuAPIClient, normalize_dpid, normalize_port_no
from src.topology.topology_loader import TopologyDefinition, TopologyLinkSpec, TopologySwitchSpec
from src.twin.config import AppConfig
from src.twin.diff_engine import StateChange, diff_network_states
from src.twin.event_engine import build_events, build_sync_error_events
from src.twin.models import EventRecord, HostState, LinkState, NetworkState, PortState, SwitchState, utc_now_iso
from src.twin.storage import InMemoryStateStore, JsonLineEventStore, JsonSnapshotStore


@dataclass(slots=True)
class SyncResult:
    """Result returned by one sync cycle."""

    state: NetworkState
    changes: list[StateChange]
    events: list[EventRecord]
    errors: list[dict[str, str]]
    sync_duration_ms: float | None = None
    api_call_count: int | None = None


def _extract_switch_payload(raw_topology_switches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        normalize_dpid(item.get("dpid", item.get("name", "unknown"))): item
        for item in raw_topology_switches
    }


def _extract_endpoint_map(raw_payload: dict[str, Any], switch_id: str) -> list[dict[str, Any]]:
    for key, value in raw_payload.items():
        if normalize_dpid(key) == switch_id:
            return value
    return []


def _parse_flag_value(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value

    text = str(value).strip().lower()
    if not text:
        return None
    try:
        if text.startswith("0x"):
            return int(text, 16)
        return int(text, 10)
    except ValueError:
        return None


def _build_port_states(
    switch_id: str,
    switch_payload: dict[str, Any],
    port_descriptions: dict[str, Any],
    port_stats: dict[str, Any],
) -> list[PortState]:
    topo_ports = switch_payload.get("ports", [])
    description_entries = _extract_endpoint_map(port_descriptions.get(switch_id, {}), switch_id)
    stat_entries = _extract_endpoint_map(port_stats.get(switch_id, {}), switch_id)

    descriptions_by_port = {}
    for entry in description_entries:
        try:
            descriptions_by_port[normalize_port_no(entry["port_no"])] = entry
        except (KeyError, ValueError):
            continue

    stats_by_port = {}
    for entry in stat_entries:
        try:
            stats_by_port[normalize_port_no(entry["port_no"])] = entry
        except (KeyError, ValueError):
            continue

    port_numbers: set[int] = set()
    for topo_port in topo_ports:
        try:
            port_numbers.add(normalize_port_no(topo_port["port_no"]))
        except (KeyError, ValueError):
            continue
    port_numbers.update(descriptions_by_port)
    port_numbers.update(stats_by_port)

    ports: list[PortState] = []
    for port_no in sorted(port_numbers):
        description = descriptions_by_port.get(port_no, {})
        stats = stats_by_port.get(port_no, {})
        state_flags = _parse_flag_value(description.get("state"))
        config_flags = _parse_flag_value(description.get("config"))
        is_up = not ((state_flags or 0) & 0x1 or (config_flags or 0) & 0x1)
        ports.append(
            PortState(
                port_no=port_no,
                rx_packets=int(stats.get("rx_packets", 0)),
                tx_packets=int(stats.get("tx_packets", 0)),
                rx_bytes=int(stats.get("rx_bytes", 0)),
                tx_bytes=int(stats.get("tx_bytes", 0)),
                is_up=is_up,
            )
        )
    return ports

def _build_switch_states(
    payload: dict[str, Any],
    switch_metadata_by_dpid: dict[str, TopologySwitchSpec] | None = None,
) -> list[SwitchState]:
    switch_payloads = _extract_switch_payload(payload.get("topology_switches", []))
    switches: list[SwitchState] = []

    for switch_id, raw_switch in sorted(switch_payloads.items()):
        metadata = (switch_metadata_by_dpid or {}).get(switch_id)
        ports = _build_port_states(
            switch_id=switch_id,
            switch_payload=raw_switch,
            port_descriptions=payload.get("port_descriptions", {}),
            port_stats=payload.get("port_stats", {}),
        )
        flow_entries = _extract_endpoint_map(payload.get("flows", {}).get(switch_id, {}), switch_id)
        switches.append(
            SwitchState(
                dpid=switch_id,
                name=metadata.name if metadata is not None else raw_switch.get("name", switch_id),
                city=raw_switch.get("city") or (metadata.city if metadata is not None else None),
                country=metadata.country if metadata is not None else None,
                latitude=metadata.latitude if metadata is not None else None,
                longitude=metadata.longitude if metadata is not None else None,
                ports=ports,
                flow_count=len(flow_entries),
            )
        )
    return switches


def _build_host_states(raw_hosts: list[dict[str, Any]]) -> list[HostState]:
    hosts: list[HostState] = []
    for raw_host in raw_hosts:
        port = raw_host.get("port", {})
        attached_switch = normalize_dpid(port.get("dpid", "unknown"))
        try:
            attached_port = normalize_port_no(port.get("port_no", 0))
        except ValueError:
            attached_port = 0
        ip = (raw_host.get("ipv4") or [""])[0]
        hosts.append(
            HostState(
                name=raw_host.get("name") or raw_host.get("mac") or ip or "unknown-host",
                ip=ip,
                mac=raw_host.get("mac", ""),
                attached_switch=attached_switch,
                attached_port=attached_port,
            )
        )
    return hosts


def _build_link_states(
    raw_links: list[dict[str, Any]],
    previous_state: NetworkState | None = None,
    preserve_previous_links: bool = False,
    link_metadata_by_dpid_pair: dict[frozenset[str], TopologyLinkSpec] | None = None,
) -> list[LinkState]:
    if preserve_previous_links and previous_state is not None:
        previous_links = previous_state.link_index()
        return [previous_links[key] for key in sorted(previous_links)]

    links_by_key: dict[str, LinkState] = {}
    for raw_link in raw_links:
        src = raw_link.get("src", {})
        dst = raw_link.get("dst", {})
        try:
            src_dpid = normalize_dpid(src["dpid"])
            dst_dpid = normalize_dpid(dst["dpid"])
            metadata = (link_metadata_by_dpid_pair or {}).get(frozenset((src_dpid, dst_dpid)))
            link = LinkState(
                src_dpid=src_dpid,
                dst_dpid=dst_dpid,
                src_port=normalize_port_no(src["port_no"]),
                dst_port=normalize_port_no(dst["port_no"]),
                is_up=True,
                latency_ms=metadata.delay_ms if metadata is not None else 0.0,
                label=metadata.label if metadata is not None else None,
                distance_km=metadata.distance_km if metadata is not None else None,
                bandwidth_mbps=metadata.bandwidth_mbps if metadata is not None else None,
            )
        except (KeyError, ValueError):
            continue
        links_by_key[link.key()] = link

    if previous_state is not None:
        for link_id, old_link in previous_state.link_index().items():
            if link_id not in links_by_key:
                links_by_key[link_id] = LinkState(
                    src_dpid=old_link.src_dpid,
                    dst_dpid=old_link.dst_dpid,
                    src_port=old_link.src_port,
                    dst_port=old_link.dst_port,
                    is_up=False,
                    latency_ms=old_link.latency_ms,
                    label=old_link.label,
                    distance_km=old_link.distance_km,
                    bandwidth_mbps=old_link.bandwidth_mbps,
                )

    return [links_by_key[key] for key in sorted(links_by_key)]


def build_network_state(
    payload: dict[str, Any],
    timestamp: str | None = None,
    previous_state: NetworkState | None = None,
    preserve_previous_links: bool = False,
    switch_metadata_by_dpid: dict[str, TopologySwitchSpec] | None = None,
    link_metadata_by_dpid_pair: dict[frozenset[str], TopologyLinkSpec] | None = None,
) -> NetworkState:
    """Build a structured network state from the raw Ryu payload."""

    return NetworkState(
        timestamp=timestamp or utc_now_iso(),
        switches=_build_switch_states(payload, switch_metadata_by_dpid=switch_metadata_by_dpid),
        links=_build_link_states(
            payload.get("links", []),
            previous_state=previous_state,
            preserve_previous_links=preserve_previous_links,
            link_metadata_by_dpid_pair=link_metadata_by_dpid_pair,
        ),
        hosts=_build_host_states(payload.get("hosts", [])),
    )


class SyncEngine:
    """Polling-based state synchronizer for the twin."""

    def __init__(
        self,
        client: RyuAPIClient,
        state_store: InMemoryStateStore,
        snapshot_store: JsonSnapshotStore | None = None,
        event_store: JsonLineEventStore | None = None,
        topology_definition: TopologyDefinition | None = None,
    ) -> None:
        self.client = client
        self.state_store = state_store
        self.snapshot_store = snapshot_store
        self.event_store = event_store
        self.switch_metadata_by_dpid = topology_definition.switches_by_dpid() if topology_definition else {}
        self.link_metadata_by_dpid_pair = (
            topology_definition.link_metadata_by_dpid_pair() if topology_definition else {}
        )

    def sync_once(self) -> SyncResult:
        started_at = time.monotonic()
        previous_state = self.state_store.get_current_state()
        payload = self.client.collect_state_payload()
        timestamp = utc_now_iso()
        fetch_status = payload.get("fetch_status", {})
        topology_switches_ok = fetch_status.get("topology_switches", True)
        topology_links_ok = fetch_status.get("links", True)
        observation_missing = (
            not payload.get("topology_switches")
            and not payload.get("links")
            and not topology_switches_ok
            and not topology_links_ok
        )

        if previous_state is not None and observation_missing:
            state = previous_state
            changes: list[StateChange] = []
        else:
            state = build_network_state(
                payload,
                timestamp=timestamp,
                previous_state=previous_state,
                preserve_previous_links=previous_state is not None and not topology_links_ok,
                switch_metadata_by_dpid=self.switch_metadata_by_dpid,
                link_metadata_by_dpid_pair=self.link_metadata_by_dpid_pair,
            )
            changes = diff_network_states(previous_state, state)

        events = build_events(changes, timestamp)
        events.extend(build_sync_error_events(payload.get("errors", []), timestamp))

        self.state_store.set_current_state(state)
        if self.snapshot_store is not None:
            self.snapshot_store.save(state)
        if self.event_store is not None:
            self.event_store.append_many(events)
        return SyncResult(
            state=state,
            changes=changes,
            events=events,
            errors=payload.get("errors", []),
            sync_duration_ms=(time.monotonic() - started_at) * 1000,
            api_call_count=payload.get("api_call_count"),
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the sync command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--print-state", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint that performs one or more sync cycles."""

    args = parse_args(argv)
    config = AppConfig()
    config.ensure_directories()

    client = RyuAPIClient(base_url=args.base_url or config.ryu_base_url)
    state_store = InMemoryStateStore()
    snapshot_store = JsonSnapshotStore(args.output.parent if args.output else config.snapshots_dir)
    event_store = JsonLineEventStore(config.events_log_path)
    engine = SyncEngine(
        client=client,
        state_store=state_store,
        snapshot_store=snapshot_store,
        event_store=event_store,
    )

    def run_once() -> SyncResult:
        result = engine.sync_once()
        if args.output:
            args.output.write_text(
                json.dumps(result.state.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if args.print_state:
            print(json.dumps(result.state.to_dict(), ensure_ascii=False, indent=2))
        if result.events:
            print(json.dumps({"events": [event.to_dict() for event in result.events]}, ensure_ascii=False))
        if result.errors:
            print(json.dumps({"sync_errors": result.errors}, ensure_ascii=False))
        return result

    if args.loop:
        interval = args.poll_interval or config.polling_interval_seconds
        while True:
            run_once()
            time.sleep(interval)
    else:
        run_once()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
