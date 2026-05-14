"""Experiment scenarios and export helpers for TER reporting."""

from __future__ import annotations

import argparse
import csv
import json
import os
from subprocess import DEVNULL, TimeoutExpired
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.controller.ryu_api_client import RyuAPIClient, normalize_dpid
from src.topology.topology_loader import TopologyDefinition, load_topology_definition
from src.twin.config import AppConfig
from src.twin.fidelity import compute_fidelity_report
from src.twin.ground_truth import build_ovs_ground_truth_state, wait_for_ovs_link_state
from src.twin.models import EventRecord
from src.twin.resource_monitor import ResourceMonitor, build_default_process_specs
from src.twin.service import TwinService


DEFAULT_SCENARIO_TARGETS: dict[str, object] = {
    "single_link_failure": ["s1", "s2"],
    "recovery_scenario": ["s1", "s2"],
    "multi_fault_scenario": [["s1", "s2"], ["s2", "s3"]],
    "link_flap_scenario": ["s1", "s2"],
    "observation_degradation_scenario": ["s1", "s2"],
}


@dataclass(slots=True)
class ExperimentRecord:
    """Structured experiment output row used for CSV export."""

    scenario_name: str
    fault_injection_timestamp: str
    detection_timestamp: str
    recovery_timestamp: str
    detection_delay: float | None
    recovery_delay: float | None
    poll_interval: float
    notes: str
    sync_mode: str | None = None
    topology_name: str | None = None
    topology_file: str | None = None
    target_link: str | None = None
    target_src_city: str | None = None
    target_dst_city: str | None = None
    target_distance_km: float | None = None
    controller_app: str | None = None
    background_traffic: str = "none"
    background_flow_count: int = 0
    background_load_percent: int | None = None
    background_target_bandwidth_mbps: float | None = None
    controller_event_queue_depth_at_detection: int | None = None
    controller_event_queue_depth_peak_until_detection: int | None = None
    controller_events_until_detection: int | None = None
    pre_fault_fidelity: float | None = None
    post_fault_fidelity: float | None = None
    post_recovery_fidelity: float | None = None
    fidelity_truth_source: str | None = None
    ground_truth_fault_timestamp: str | None = None
    ground_truth_recovery_timestamp: str | None = None
    ground_truth_detection_lag: float | None = None
    ground_truth_recovery_lag: float | None = None
    node_count: int | None = None
    link_count: int | None = None
    sync_duration_ms: float | None = None
    api_call_count: int | None = None
    pre_fault_total_packets: int | None = None
    pre_fault_total_bytes: int | None = None
    post_detection_total_packets: int | None = None
    post_detection_total_bytes: int | None = None
    post_recovery_total_packets: int | None = None
    post_recovery_total_bytes: int | None = None
    resource_log_file: str | None = None
    Run_Order: int | None = None
    repeat_index: int = 1
    configured_repeat_count: int = 1

    def to_row(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class HostEndpoint:
    """Stable host endpoint metadata used to build background traffic flows."""

    name: str
    ip: str


@dataclass(slots=True)
class BackgroundTrafficConfig:
    """Runtime knobs for optional background traffic during experiments."""

    profile: str = "none"
    ping_interval_seconds: float = 0.2
    iperf_parallel_streams: int = 2
    iperf_duration_seconds: int = 3600
    iperf_bandwidth_mbps: float | None = None
    load_percent: int | None = None


class BackgroundTrafficSession:
    """Lifecycle wrapper for background traffic processes started inside Mininet hosts."""

    def __init__(self, processes: list[object], flow_count: int) -> None:
        self._processes = processes
        self.flow_count = flow_count

    def stop(self) -> None:
        for process in self._processes:
            if getattr(process, "poll")() is None:
                getattr(process, "terminate")()
        for process in self._processes:
            try:
                getattr(process, "wait")(timeout=1)
            except TimeoutExpired:
                getattr(process, "kill")()
                getattr(process, "wait")(timeout=1)


class FaultInjectingRyuClient:
    """Wrapper that injects endpoint-specific observation degradation for experiments."""

    def __init__(
        self,
        base_client: RyuAPIClient,
        degraded_attempts: set[int] | None = None,
        degraded_endpoint: str = "/v1.0/topology/links",
    ) -> None:
        self.base_client = base_client
        self.degraded_attempts = degraded_attempts or {2}
        self.degraded_endpoint = degraded_endpoint
        self.collect_count = 0

    def collect_state_payload(self) -> dict[str, Any]:
        self.collect_count += 1
        payload = dict(self.base_client.collect_state_payload())
        if self.collect_count not in self.degraded_attempts:
            return payload

        errors = [dict(error) for error in payload.get("errors", [])]
        errors.append(
            {
                "endpoint": self.degraded_endpoint,
                "message": "Injected observation degradation for experiment",
            }
        )
        fetch_status = dict(payload.get("fetch_status", {}))
        fetch_status["links"] = False

        degraded_payload = dict(payload)
        degraded_payload["links"] = []
        degraded_payload["errors"] = errors
        degraded_payload["fetch_status"] = fetch_status
        return degraded_payload

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base_client, name)


@dataclass(slots=True)
class ExperimentStatsRow:
    """Grouped summary statistics for repeated experiment runs."""

    scenario_name: str
    sync_mode: str | None
    topology_name: str | None
    topology_file: str | None
    target_link: str | None
    controller_app: str | None
    background_traffic: str
    background_load_percent: int | None
    background_target_bandwidth_mbps: float | None
    configured_repeat_count: int
    poll_interval: float | None
    samples: int
    detection_samples: int
    detection_mean: float | None
    detection_p95: float | None
    detection_stddev: float | None
    recovery_samples: int
    recovery_mean: float | None
    recovery_p95: float | None
    recovery_stddev: float | None

    def to_row(self) -> dict[str, object]:
        return asdict(self)


def parse_iso_timestamp(value: str) -> datetime:
    """Parse a stable ISO 8601 timestamp."""

    return datetime.fromisoformat(value)


def compute_delay_seconds(start_timestamp: str, end_timestamp: str) -> float:
    """Compute the delay between two timestamps in seconds."""

    return (parse_iso_timestamp(end_timestamp) - parse_iso_timestamp(start_timestamp)).total_seconds()


def write_experiment_results(records: list[ExperimentRecord], csv_path: Path) -> Path:
    """Write experiment records to CSV for downstream analysis."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ExperimentRecord.__dataclass_fields__.keys()))
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_row())
    return csv_path


def write_experiment_summary(records: list[ExperimentRecord], json_path: Path) -> Path:
    """Write a JSON summary of the produced experiment records."""

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps([record.to_row() for record in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return json_path


def _compute_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _compute_stddev(values: list[float]) -> float | None:
    if len(values) < 2:
        return 0.0 if values else None
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return variance ** 0.5


def _compute_p95(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, int((len(sorted_values) - 1) * 0.95)))
    return sorted_values[index]


def summarize_experiment_records(records: list[ExperimentRecord]) -> list[ExperimentStatsRow]:
    """Group repeated experiment rows by scenario and compute summary statistics."""

    grouped: dict[
        tuple[str, str | None, str | None, str | None, str | None, str, int | None, float | None, int, float],
        list[ExperimentRecord],
    ] = {}
    for record in records:
        key = (
            record.scenario_name,
            record.sync_mode,
            record.topology_name,
            record.topology_file,
            record.target_link,
            record.background_traffic,
            record.background_load_percent,
            record.background_target_bandwidth_mbps,
            record.configured_repeat_count,
            record.poll_interval,
        )
        grouped.setdefault(key, []).append(record)

    summary_rows: list[ExperimentStatsRow] = []
    for key, group in grouped.items():
        (
            scenario_name,
            sync_mode,
            topology_name,
            topology_file,
            target_link,
            background_traffic,
            background_load_percent,
            background_target_bandwidth_mbps,
            configured_repeat_count,
            poll_interval,
        ) = key
        detection_values = [record.detection_delay for record in group if record.detection_delay is not None]
        recovery_values = [record.recovery_delay for record in group if record.recovery_delay is not None]
        summary_rows.append(
            ExperimentStatsRow(
                scenario_name=scenario_name,
                sync_mode=sync_mode,
                topology_name=topology_name,
                topology_file=topology_file,
                target_link=target_link,
                controller_app=group[0].controller_app,
                background_traffic=background_traffic,
                background_load_percent=background_load_percent,
                background_target_bandwidth_mbps=background_target_bandwidth_mbps,
                configured_repeat_count=configured_repeat_count,
                poll_interval=poll_interval,
                samples=len(group),
                detection_samples=len(detection_values),
                detection_mean=_compute_mean(detection_values),
                detection_p95=_compute_p95(detection_values),
                detection_stddev=_compute_stddev(detection_values),
                recovery_samples=len(recovery_values),
                recovery_mean=_compute_mean(recovery_values),
                recovery_p95=_compute_p95(recovery_values),
                recovery_stddev=_compute_stddev(recovery_values),
            )
        )
    return sorted(
        summary_rows,
        key=lambda row: (
            row.sync_mode or "",
            row.topology_name or "",
            row.scenario_name,
            row.target_link or "",
            row.background_traffic,
        ),
    )


def write_experiment_statistics(summary_rows: list[ExperimentStatsRow], csv_path: Path, json_path: Path) -> tuple[Path, Path]:
    """Write grouped summary statistics for repeated experiments."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ExperimentStatsRow.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row.to_row())

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps([row.to_row() for row in summary_rows], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return csv_path, json_path


def _event_record_from_dict(payload: dict[str, object]) -> EventRecord:
    return EventRecord(
        timestamp=str(payload.get("timestamp", "")),
        event_type=str(payload.get("event_type", "")),
        entity_type=str(payload.get("entity_type", "")),
        entity_id=str(payload.get("entity_id", "")),
        old_value=payload.get("old_value"),
        new_value=payload.get("new_value"),
        details=dict(payload.get("details", {})),
    )


def _wait_for_event(
    service: TwinService,
    event_type: str,
    timeout_seconds: float,
    sleep_seconds: float,
    entity_id: str | None = None,
    not_before_timestamp: str | None = None,
) -> EventRecord | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for payload in service.get_events(limit=0):
            event = _event_record_from_dict(payload)
            if event.event_type != event_type:
                continue
            if entity_id is not None and event.entity_id != entity_id:
                continue
            if (
                not_before_timestamp is not None
                and parse_iso_timestamp(event.timestamp) < parse_iso_timestamp(not_before_timestamp)
            ):
                continue
            return event
        time.sleep(sleep_seconds)
    return None


def _topology_is_ready(service: TwinService) -> bool:
    state = service.get_state()
    return bool(state.get("switches")) and bool(state.get("links"))


def _wait_for_initial_state(service: TwinService, timeout_seconds: float, sleep_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if service.health().get("has_state") and _topology_is_ready(service):
            return
        time.sleep(sleep_seconds)
    raise TimeoutError("Timed out waiting for the initial twin state.")


def _controller_event_queue_metrics(
    event_stream_path: Path,
    fault_injection_timestamp: str,
    detection_timestamp: str,
) -> dict[str, int | None]:
    """Approximate controller-side backlog around one detected event from the JSONL stream."""

    if not detection_timestamp or not event_stream_path.exists():
        return {
            "controller_event_queue_depth_at_detection": None,
            "controller_event_queue_depth_peak_until_detection": None,
            "controller_events_until_detection": None,
        }

    fault_dt = parse_iso_timestamp(fault_injection_timestamp)
    detection_dt = parse_iso_timestamp(detection_timestamp)
    matching_events: list[dict[str, object]] = []
    with event_stream_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            raw_timestamp = payload.get("timestamp")
            if not raw_timestamp:
                continue
            try:
                event_dt = parse_iso_timestamp(str(raw_timestamp))
            except ValueError:
                continue
            if fault_dt <= event_dt <= detection_dt:
                matching_events.append(payload)

    if not matching_events:
        return {
            "controller_event_queue_depth_at_detection": None,
            "controller_event_queue_depth_peak_until_detection": None,
            "controller_events_until_detection": 0,
        }

    queue_depths = [
        int(payload["queue_depth_after_put"])
        for payload in matching_events
        if payload.get("queue_depth_after_put") not in (None, "")
    ]
    last_depth = queue_depths[-1] if queue_depths else None
    peak_depth = max(queue_depths) if queue_depths else None
    return {
        "controller_event_queue_depth_at_detection": last_depth,
        "controller_event_queue_depth_peak_until_detection": peak_depth,
        "controller_events_until_detection": len(matching_events),
    }


def _initialization_timeout(service: TwinService, fallback_timeout_seconds: float) -> float:
    return float(getattr(service.config, "initialization_timeout_seconds", fallback_timeout_seconds))


def _resolve_switch_id(service: TwinService, switch_ref: str) -> str:
    state = service.get_state()
    switches = state.get("switches", [])
    for switch in switches:
        if switch["dpid"] == switch_ref:
            return switch_ref
    for switch in switches:
        if switch["name"] == switch_ref:
            return switch["dpid"]
    if switch_ref.startswith("s") and switch_ref[1:].isdigit():
        candidate_dpid = normalize_dpid(int(switch_ref[1:]))
        for switch in switches:
            if switch["dpid"] == candidate_dpid:
                return candidate_dpid
    raise ValueError(f"Switch {switch_ref!r} not found in the current twin state.")


def _link_id_for_pair(service: TwinService, src_switch: str, dst_switch: str) -> str:
    src_switch_id = _resolve_switch_id(service, src_switch)
    dst_switch_id = _resolve_switch_id(service, dst_switch)
    expected_endpoints = {src_switch_id, dst_switch_id}
    state = service.get_state()
    for link in state.get("links", []):
        endpoints = {link["src_dpid"], link["dst_dpid"]}
        if endpoints == expected_endpoints:
            return link["link_id"]
    raise ValueError(f"Link between {src_switch!r} and {dst_switch!r} not found in the current twin state.")


def _scenario_link_targets(
    scenario_name: str,
    topology_definition: TopologyDefinition | None = None,
) -> list[tuple[str, str]]:
    raw_targets = None
    if topology_definition is not None:
        raw_targets = topology_definition.scenario_targets.get(scenario_name)
    if raw_targets is None:
        raw_targets = DEFAULT_SCENARIO_TARGETS.get(scenario_name)
    if raw_targets is None:
        raise ValueError(f"Unsupported scenario: {scenario_name}")

    candidate_pairs = raw_targets if scenario_name == "multi_fault_scenario" else [raw_targets]
    targets: list[tuple[str, str]] = []
    for pair in candidate_pairs:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError(f"Scenario target for {scenario_name!r} must be a two-switch pair.")
        targets.append((str(pair[0]), str(pair[1])))
    return targets


def _target_metadata(
    topology_definition: TopologyDefinition | None,
    src_switch: str,
    dst_switch: str,
) -> dict[str, object]:
    if topology_definition is None:
        return {
            "topology_name": "minimal_demo",
            "topology_file": None,
            "target_link": f"{src_switch}-{dst_switch}",
            "target_src_city": None,
            "target_dst_city": None,
            "target_distance_km": None,
        }

    switches_by_name = topology_definition.switches_by_name()
    link = topology_definition.link_for_switch_pair(src_switch, dst_switch)
    src_city = switches_by_name[src_switch].city if src_switch in switches_by_name else None
    dst_city = switches_by_name[dst_switch].city if dst_switch in switches_by_name else None
    human_link_label = f"{src_city}-{dst_city}" if src_city and dst_city else None
    return {
        "topology_name": topology_definition.name,
        "topology_file": str(topology_definition.provenance.get("subset_source", "")) or None,
        "target_link": human_link_label or (link.label if link is not None and link.label else f"{src_switch}-{dst_switch}"),
        "target_src_city": src_city,
        "target_dst_city": dst_city,
        "target_distance_km": link.distance_km if link is not None else None,
    }


def _host_endpoints(network, topology_definition: TopologyDefinition | None = None) -> list[HostEndpoint]:
    if topology_definition is not None:
        return [HostEndpoint(name=host.name, ip=host.ip.split("/")[0]) for host in topology_definition.hosts]
    return [HostEndpoint(name=host.name, ip=host.IP()) for host in sorted(network.hosts, key=lambda item: item.name)]


def _background_traffic_pairs(endpoints: list[HostEndpoint]) -> list[tuple[HostEndpoint, HostEndpoint]]:
    pairs: list[tuple[HostEndpoint, HostEndpoint]] = []
    for index in range(len(endpoints) // 2):
        src_endpoint = endpoints[index]
        dst_endpoint = endpoints[-(index + 1)]
        if src_endpoint.name == dst_endpoint.name:
            continue
        pairs.append((src_endpoint, dst_endpoint))
    return pairs


def _switch_port_index(state: dict[str, Any]) -> dict[tuple[str, int], dict[str, Any]]:
    index: dict[tuple[str, int], dict[str, Any]] = {}
    for switch in state.get("switches", []):
        dpid = str(switch.get("dpid", ""))
        for port in switch.get("ports", []):
            try:
                index[(dpid, int(port.get("port_no", 0)))] = port
            except (TypeError, ValueError):
                continue
    return index


def _link_counter_snapshot(service: TwinService, link_id: str) -> dict[str, int] | None:
    state = service.get_state()
    port_index = _switch_port_index(state)
    for link in state.get("links", []):
        if link.get("link_id") != link_id:
            continue
        src_key = (str(link.get("src_dpid", "")), int(link.get("src_port", 0)))
        dst_key = (str(link.get("dst_dpid", "")), int(link.get("dst_port", 0)))
        src_port = port_index.get(src_key)
        dst_port = port_index.get(dst_key)
        if src_port is None or dst_port is None:
            return None
        rx_packets = int(src_port.get("rx_packets", 0)) + int(dst_port.get("rx_packets", 0))
        tx_packets = int(src_port.get("tx_packets", 0)) + int(dst_port.get("tx_packets", 0))
        rx_bytes = int(src_port.get("rx_bytes", 0)) + int(dst_port.get("rx_bytes", 0))
        tx_bytes = int(src_port.get("tx_bytes", 0)) + int(dst_port.get("tx_bytes", 0))
    return {
        "rx_packets": rx_packets,
        "tx_packets": tx_packets,
        "rx_bytes": rx_bytes,
        "tx_bytes": tx_bytes,
        "total_packets": rx_packets + tx_packets,
        "total_bytes": rx_bytes + tx_bytes,
    }


def _current_twin_state(service: TwinService):
    if hasattr(service, "state_store"):
        state = service.state_store.get_current_state()
        if state is not None:
            return state
    if hasattr(service, "get_state"):
        payload = service.get_state()
        if isinstance(payload, dict):
            return payload
    return None


def _capture_fidelity_score(
    service: TwinService,
    network=None,
    topology_definition: TopologyDefinition | None = None,
) -> tuple[float | None, str | None]:
    """Capture fidelity, preferring independent OVS truth when the runtime is available."""

    twin_state = _current_twin_state(service)
    if twin_state is not None and network is not None and not isinstance(twin_state, dict):
        try:
            ground_truth_state = build_ovs_ground_truth_state(
                network,
                topology_definition=topology_definition,
                timestamp=twin_state.timestamp,
            )
            return compute_fidelity_report(twin_state, ground_truth_state).overall_fidelity, "ovs_mininet"
        except Exception:
            pass

    try:
        return service.get_fidelity_report().overall_fidelity, "ryu_api"
    except Exception:
        return None, None


def _capture_runtime_metrics(service: TwinService) -> dict[str, int | float | None]:
    """Capture runtime metrics from the latest twin state and sync result."""

    state = None
    if hasattr(service, "state_store"):
        state = service.state_store.get_current_state()
    if state is None and hasattr(service, "get_state"):
        payload = service.get_state()
        state = payload if isinstance(payload, dict) else None
    last_result = getattr(service, "_last_result", None)

    if state is not None and not isinstance(state, dict):
        node_count = len(state.switches)
        link_count = len(state.links)
    else:
        node_count = len(state.get("switches", [])) if state is not None else None
        link_count = len(state.get("links", [])) if state is not None else None

    return {
        "node_count": node_count,
        "link_count": link_count,
        "sync_duration_ms": last_result.sync_duration_ms if last_result is not None else None,
        "api_call_count": last_result.api_call_count if last_result is not None else None,
    }
    return None


def _first_truth_source(*sources: str | None) -> str | None:
    for source in sources:
        if source:
            return source
    return None


def _ground_truth_lag(truth_timestamp: str | None, twin_timestamp: str) -> float | None:
    if truth_timestamp in (None, "") or not twin_timestamp:
        return None
    return compute_delay_seconds(str(truth_timestamp), twin_timestamp)


def _start_background_traffic(
    network,
    topology_definition: TopologyDefinition | None,
    traffic_config: BackgroundTrafficConfig,
) -> BackgroundTrafficSession:
    if traffic_config.profile == "none":
        return BackgroundTrafficSession(processes=[], flow_count=0)
    if traffic_config.profile not in {"icmp", "iperf_tcp"}:
        raise ValueError(f"Unsupported background traffic profile: {traffic_config.profile}")

    endpoints = _host_endpoints(network, topology_definition)
    pairs = _background_traffic_pairs(endpoints)
    processes: list[object] = []
    if traffic_config.profile == "iperf_tcp":
        discovery_host = network.get(endpoints[0].name)
        traffic_binary = discovery_host.cmd("command -v iperf3 || command -v iperf").strip()
        if not traffic_binary:
            raise ValueError("iperf background traffic requested, but neither iperf3 nor iperf is installed.")
        if traffic_config.iperf_bandwidth_mbps is not None and not traffic_binary.endswith("iperf3"):
            raise ValueError("Bandwidth-shaped iperf background traffic requires iperf3.")
        for endpoint in endpoints:
            host = network.get(endpoint.name)
            processes.append(
                host.popen(
                    ["sh", "-lc", f"exec {traffic_binary} -s"],
                    stdout=DEVNULL,
                    stderr=DEVNULL,
                )
            )
        time.sleep(1.0)
        for src_endpoint, dst_endpoint in pairs:
            src_host = network.get(src_endpoint.name)
            bitrate_args = ""
            if traffic_config.iperf_bandwidth_mbps is not None:
                bitrate_args = f" -b {traffic_config.iperf_bandwidth_mbps}M"
            if traffic_binary.endswith("iperf3"):
                client_command = (
                    f"exec {traffic_binary} -c {dst_endpoint.ip} "
                    f"-t {traffic_config.iperf_duration_seconds} -P {traffic_config.iperf_parallel_streams}"
                    f"{bitrate_args}"
                )
            else:
                client_command = (
                    f"exec {traffic_binary} -c {dst_endpoint.ip} "
                    f"-t {traffic_config.iperf_duration_seconds} -P {traffic_config.iperf_parallel_streams}"
                )
            processes.append(
                src_host.popen(
                    ["sh", "-lc", client_command],
                    stdout=DEVNULL,
                    stderr=DEVNULL,
                )
            )
        return BackgroundTrafficSession(processes=processes, flow_count=len(processes))

    for src_endpoint, dst_endpoint in pairs:
        src_host = network.get(src_endpoint.name)
        dst_host = network.get(dst_endpoint.name)
        processes.append(
            src_host.popen(
                ["ping", "-i", str(traffic_config.ping_interval_seconds), dst_endpoint.ip],
                stdout=DEVNULL,
                stderr=DEVNULL,
            )
        )
        processes.append(
            dst_host.popen(
                ["ping", "-i", str(traffic_config.ping_interval_seconds), src_endpoint.ip],
                stdout=DEVNULL,
                stderr=DEVNULL,
            )
        )
    return BackgroundTrafficSession(processes=processes, flow_count=len(processes))


def _run_single_link_failure_runtime(
    service: TwinService,
    network,
    src_switch: str = "s1",
    dst_switch: str = "s2",
    topology_definition: TopologyDefinition | None = None,
    timeout_seconds: float = 20.0,
    resource_monitor: ResourceMonitor | None = None,
) -> ExperimentRecord:
    _wait_for_initial_state(service, timeout_seconds=_initialization_timeout(service, timeout_seconds), sleep_seconds=0.1)
    link_id = _link_id_for_pair(service, src_switch, dst_switch)
    target_metadata = _target_metadata(topology_definition, src_switch, dst_switch)
    pre_fault_fidelity, fidelity_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    pre_fault_counters = _link_counter_snapshot(service, link_id)

    fault_time = datetime.now().astimezone().isoformat()
    if resource_monitor is not None:
        resource_monitor.mark_event("fault_injected", timestamp=fault_time)
    network.configLinkStatus(src_switch, dst_switch, "down")
    ground_truth_fault_timestamp = wait_for_ovs_link_state(
        network,
        src_switch,
        dst_switch,
        expected_up=False,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    post_fault_fidelity, post_fault_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    down_event = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=timeout_seconds,
        sleep_seconds=min(service.config.polling_interval_seconds / 4, 0.5),
        entity_id=link_id,
        not_before_timestamp=fault_time,
    )

    detection_timestamp = down_event.timestamp if down_event is not None else ""
    detection_delay = (
        compute_delay_seconds(fault_time, detection_timestamp) if detection_timestamp else None
    )
    post_detection_counters = _link_counter_snapshot(service, link_id)
    runtime_metrics = _capture_runtime_metrics(service)

    return ExperimentRecord(
        scenario_name="single_link_failure",
        topology_name=target_metadata["topology_name"],
        target_link=target_metadata["target_link"],
        target_src_city=target_metadata["target_src_city"],
        target_dst_city=target_metadata["target_dst_city"],
        target_distance_km=target_metadata["target_distance_km"],
        fault_injection_timestamp=fault_time,
        detection_timestamp=detection_timestamp,
        recovery_timestamp="",
        detection_delay=detection_delay,
        recovery_delay=None,
        poll_interval=service.config.polling_interval_seconds,
        notes=f"Expected one LINK_DOWN event after bringing {src_switch}-{dst_switch} down.",
        pre_fault_fidelity=pre_fault_fidelity,
        post_fault_fidelity=post_fault_fidelity,
        fidelity_truth_source=_first_truth_source(fidelity_truth_source, post_fault_truth_source),
        ground_truth_fault_timestamp=ground_truth_fault_timestamp,
        ground_truth_detection_lag=_ground_truth_lag(ground_truth_fault_timestamp, detection_timestamp),
        node_count=runtime_metrics["node_count"],
        link_count=runtime_metrics["link_count"],
        sync_duration_ms=runtime_metrics["sync_duration_ms"],
        api_call_count=runtime_metrics["api_call_count"],
        pre_fault_total_packets=pre_fault_counters.get("total_packets") if pre_fault_counters else None,
        pre_fault_total_bytes=pre_fault_counters.get("total_bytes") if pre_fault_counters else None,
        post_detection_total_packets=post_detection_counters.get("total_packets") if post_detection_counters else None,
        post_detection_total_bytes=post_detection_counters.get("total_bytes") if post_detection_counters else None,
    )


def _run_recovery_runtime(
    service: TwinService,
    network,
    src_switch: str = "s1",
    dst_switch: str = "s2",
    topology_definition: TopologyDefinition | None = None,
    timeout_seconds: float = 20.0,
    resource_monitor: ResourceMonitor | None = None,
) -> ExperimentRecord:
    _wait_for_initial_state(service, timeout_seconds=_initialization_timeout(service, timeout_seconds), sleep_seconds=0.1)
    link_id = _link_id_for_pair(service, src_switch, dst_switch)
    target_metadata = _target_metadata(topology_definition, src_switch, dst_switch)
    pre_fault_fidelity, pre_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    pre_fault_counters = _link_counter_snapshot(service, link_id)

    fault_time = datetime.now().astimezone().isoformat()
    if resource_monitor is not None:
        resource_monitor.mark_event("fault_injected", timestamp=fault_time)
    network.configLinkStatus(src_switch, dst_switch, "down")
    ground_truth_fault_timestamp = wait_for_ovs_link_state(
        network,
        src_switch,
        dst_switch,
        expected_up=False,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    post_fault_fidelity, post_fault_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    down_event = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=timeout_seconds,
        sleep_seconds=min(service.config.polling_interval_seconds / 4, 0.5),
        entity_id=link_id,
        not_before_timestamp=fault_time,
    )
    post_detection_counters = _link_counter_snapshot(service, link_id)

    recovery_time = datetime.now().astimezone().isoformat()
    if resource_monitor is not None:
        resource_monitor.mark_event("recovery_requested", timestamp=recovery_time)
    network.configLinkStatus(src_switch, dst_switch, "up")
    ground_truth_recovery_timestamp = wait_for_ovs_link_state(
        network,
        src_switch,
        dst_switch,
        expected_up=True,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    post_recovery_fidelity, post_recovery_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    up_event = _wait_for_event(
        service=service,
        event_type="LINK_UP",
        timeout_seconds=timeout_seconds,
        sleep_seconds=min(service.config.polling_interval_seconds / 4, 0.5),
        entity_id=link_id,
        not_before_timestamp=recovery_time,
    )

    detection_timestamp = down_event.timestamp if down_event is not None else ""
    recovery_timestamp = up_event.timestamp if up_event is not None else ""
    post_recovery_counters = _link_counter_snapshot(service, link_id)
    runtime_metrics = _capture_runtime_metrics(service)

    return ExperimentRecord(
        scenario_name="recovery_scenario",
        topology_name=target_metadata["topology_name"],
        target_link=target_metadata["target_link"],
        target_src_city=target_metadata["target_src_city"],
        target_dst_city=target_metadata["target_dst_city"],
        target_distance_km=target_metadata["target_distance_km"],
        fault_injection_timestamp=fault_time,
        detection_timestamp=detection_timestamp,
        recovery_timestamp=recovery_timestamp,
        detection_delay=compute_delay_seconds(fault_time, detection_timestamp) if detection_timestamp else None,
        recovery_delay=compute_delay_seconds(recovery_time, recovery_timestamp) if recovery_timestamp else None,
        poll_interval=service.config.polling_interval_seconds,
        notes=f"Expected LINK_DOWN followed by LINK_UP for {src_switch}-{dst_switch}.",
        pre_fault_fidelity=pre_fault_fidelity,
        post_fault_fidelity=post_fault_fidelity,
        post_recovery_fidelity=post_recovery_fidelity,
        fidelity_truth_source=_first_truth_source(
            pre_truth_source,
            post_fault_truth_source,
            post_recovery_truth_source,
        ),
        ground_truth_fault_timestamp=ground_truth_fault_timestamp,
        ground_truth_recovery_timestamp=ground_truth_recovery_timestamp,
        ground_truth_detection_lag=_ground_truth_lag(ground_truth_fault_timestamp, detection_timestamp),
        ground_truth_recovery_lag=_ground_truth_lag(ground_truth_recovery_timestamp, recovery_timestamp),
        node_count=runtime_metrics["node_count"],
        link_count=runtime_metrics["link_count"],
        sync_duration_ms=runtime_metrics["sync_duration_ms"],
        api_call_count=runtime_metrics["api_call_count"],
        pre_fault_total_packets=pre_fault_counters.get("total_packets") if pre_fault_counters else None,
        pre_fault_total_bytes=pre_fault_counters.get("total_bytes") if pre_fault_counters else None,
        post_detection_total_packets=post_detection_counters.get("total_packets") if post_detection_counters else None,
        post_detection_total_bytes=post_detection_counters.get("total_bytes") if post_detection_counters else None,
        post_recovery_total_packets=post_recovery_counters.get("total_packets") if post_recovery_counters else None,
        post_recovery_total_bytes=post_recovery_counters.get("total_bytes") if post_recovery_counters else None,
    )


def _run_multi_fault_runtime(
    service: TwinService,
    network,
    first_target: tuple[str, str] = ("s1", "s2"),
    second_target: tuple[str, str] = ("s2", "s3"),
    topology_definition: TopologyDefinition | None = None,
    timeout_seconds: float = 20.0,
    resource_monitor: ResourceMonitor | None = None,
) -> list[ExperimentRecord]:
    _wait_for_initial_state(service, timeout_seconds=_initialization_timeout(service, timeout_seconds), sleep_seconds=0.1)
    first_src_switch, first_dst_switch = first_target
    second_src_switch, second_dst_switch = second_target
    first_target_metadata = _target_metadata(topology_definition, first_src_switch, first_dst_switch)
    second_target_metadata = _target_metadata(topology_definition, second_src_switch, second_dst_switch)
    first_link_id = _link_id_for_pair(service, first_src_switch, first_dst_switch)
    second_link_id = _link_id_for_pair(service, second_src_switch, second_dst_switch)
    first_pre_fault_fidelity, first_pre_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    first_pre_fault_counters = _link_counter_snapshot(service, first_link_id)
    first_fault_time = datetime.now().astimezone().isoformat()
    if resource_monitor is not None:
        resource_monitor.mark_event("fault_injected_1", timestamp=first_fault_time)
    network.configLinkStatus(first_src_switch, first_dst_switch, "down")
    first_ground_truth_fault_timestamp = wait_for_ovs_link_state(
        network,
        first_src_switch,
        first_dst_switch,
        expected_up=False,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    first_post_fault_fidelity, first_post_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    first_event = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=timeout_seconds,
        sleep_seconds=min(service.config.polling_interval_seconds / 4, 0.5),
        entity_id=first_link_id,
        not_before_timestamp=first_fault_time,
    )
    first_post_detection_counters = _link_counter_snapshot(service, first_link_id)

    second_fault_time = datetime.now().astimezone().isoformat()
    second_pre_fault_fidelity, second_pre_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    second_pre_fault_counters = _link_counter_snapshot(service, second_link_id)
    if resource_monitor is not None:
        resource_monitor.mark_event("fault_injected_2", timestamp=second_fault_time)
    network.configLinkStatus(second_src_switch, second_dst_switch, "down")
    second_ground_truth_fault_timestamp = wait_for_ovs_link_state(
        network,
        second_src_switch,
        second_dst_switch,
        expected_up=False,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    second_post_fault_fidelity, second_post_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    second_event = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=timeout_seconds,
        sleep_seconds=min(service.config.polling_interval_seconds / 4, 0.5),
        entity_id=second_link_id,
        not_before_timestamp=second_fault_time,
    )
    second_post_detection_counters = _link_counter_snapshot(service, second_link_id)
    runtime_metrics = _capture_runtime_metrics(service)

    return [
        ExperimentRecord(
            scenario_name="multi_fault_scenario_fault_1",
            topology_name=first_target_metadata["topology_name"],
            target_link=first_target_metadata["target_link"],
            target_src_city=first_target_metadata["target_src_city"],
            target_dst_city=first_target_metadata["target_dst_city"],
            target_distance_km=first_target_metadata["target_distance_km"],
            fault_injection_timestamp=first_fault_time,
            detection_timestamp=first_event.timestamp if first_event else "",
            recovery_timestamp="",
            detection_delay=compute_delay_seconds(first_fault_time, first_event.timestamp)
            if first_event
            else None,
            recovery_delay=None,
            poll_interval=service.config.polling_interval_seconds,
            notes=f"First LINK_DOWN event after bringing {first_src_switch}-{first_dst_switch} down.",
            pre_fault_fidelity=first_pre_fault_fidelity,
            post_fault_fidelity=first_post_fault_fidelity,
            fidelity_truth_source=_first_truth_source(first_pre_truth_source, first_post_truth_source),
            ground_truth_fault_timestamp=first_ground_truth_fault_timestamp,
            ground_truth_detection_lag=_ground_truth_lag(
                first_ground_truth_fault_timestamp,
                first_event.timestamp if first_event else "",
            ),
            node_count=runtime_metrics["node_count"],
            link_count=runtime_metrics["link_count"],
            sync_duration_ms=runtime_metrics["sync_duration_ms"],
            api_call_count=runtime_metrics["api_call_count"],
            pre_fault_total_packets=first_pre_fault_counters.get("total_packets") if first_pre_fault_counters else None,
            pre_fault_total_bytes=first_pre_fault_counters.get("total_bytes") if first_pre_fault_counters else None,
            post_detection_total_packets=(
                first_post_detection_counters.get("total_packets") if first_post_detection_counters else None
            ),
            post_detection_total_bytes=(
                first_post_detection_counters.get("total_bytes") if first_post_detection_counters else None
            ),
        ),
        ExperimentRecord(
            scenario_name="multi_fault_scenario_fault_2",
            topology_name=second_target_metadata["topology_name"],
            target_link=second_target_metadata["target_link"],
            target_src_city=second_target_metadata["target_src_city"],
            target_dst_city=second_target_metadata["target_dst_city"],
            target_distance_km=second_target_metadata["target_distance_km"],
            fault_injection_timestamp=second_fault_time,
            detection_timestamp=second_event.timestamp if second_event else "",
            recovery_timestamp="",
            detection_delay=compute_delay_seconds(second_fault_time, second_event.timestamp)
            if second_event
            else None,
            recovery_delay=None,
            poll_interval=service.config.polling_interval_seconds,
            notes=f"Second LINK_DOWN event after bringing {second_src_switch}-{second_dst_switch} down.",
            pre_fault_fidelity=second_pre_fault_fidelity,
            post_fault_fidelity=second_post_fault_fidelity,
            fidelity_truth_source=_first_truth_source(second_pre_truth_source, second_post_truth_source),
            ground_truth_fault_timestamp=second_ground_truth_fault_timestamp,
            ground_truth_detection_lag=_ground_truth_lag(
                second_ground_truth_fault_timestamp,
                second_event.timestamp if second_event else "",
            ),
            node_count=runtime_metrics["node_count"],
            link_count=runtime_metrics["link_count"],
            sync_duration_ms=runtime_metrics["sync_duration_ms"],
            api_call_count=runtime_metrics["api_call_count"],
            pre_fault_total_packets=second_pre_fault_counters.get("total_packets") if second_pre_fault_counters else None,
            pre_fault_total_bytes=second_pre_fault_counters.get("total_bytes") if second_pre_fault_counters else None,
            post_detection_total_packets=(
                second_post_detection_counters.get("total_packets") if second_post_detection_counters else None
            ),
            post_detection_total_bytes=(
                second_post_detection_counters.get("total_bytes") if second_post_detection_counters else None
            ),
        ),
    ]


def _run_link_flap_runtime(
    service: TwinService,
    network,
    src_switch: str = "s1",
    dst_switch: str = "s2",
    topology_definition: TopologyDefinition | None = None,
    timeout_seconds: float = 20.0,
    resource_monitor: ResourceMonitor | None = None,
) -> list[ExperimentRecord]:
    _wait_for_initial_state(service, timeout_seconds=_initialization_timeout(service, timeout_seconds), sleep_seconds=0.1)
    link_id = _link_id_for_pair(service, src_switch, dst_switch)
    target_metadata = _target_metadata(topology_definition, src_switch, dst_switch)
    pre_fault_fidelity, pre_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    pre_fault_counters = _link_counter_snapshot(service, link_id)

    sleep_seconds = min(service.config.polling_interval_seconds / 4, 0.5)

    first_down_time = datetime.now().astimezone().isoformat()
    if resource_monitor is not None:
        resource_monitor.mark_event("fault_injected_1", timestamp=first_down_time)
    network.configLinkStatus(src_switch, dst_switch, "down")
    first_ground_truth_fault_timestamp = wait_for_ovs_link_state(
        network,
        src_switch,
        dst_switch,
        expected_up=False,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    first_post_fault_fidelity, first_post_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    first_down_event = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=timeout_seconds,
        sleep_seconds=sleep_seconds,
        entity_id=link_id,
        not_before_timestamp=first_down_time,
    )
    first_detection_counters = _link_counter_snapshot(service, link_id)

    up_time = datetime.now().astimezone().isoformat()
    pre_recovery_fidelity, pre_recovery_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    if resource_monitor is not None:
        resource_monitor.mark_event("recovery_requested", timestamp=up_time)
    network.configLinkStatus(src_switch, dst_switch, "up")
    ground_truth_recovery_timestamp = wait_for_ovs_link_state(
        network,
        src_switch,
        dst_switch,
        expected_up=True,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    post_recovery_fidelity, post_recovery_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    up_event = _wait_for_event(
        service=service,
        event_type="LINK_UP",
        timeout_seconds=timeout_seconds,
        sleep_seconds=sleep_seconds,
        entity_id=link_id,
        not_before_timestamp=up_time,
    )
    post_recovery_counters = _link_counter_snapshot(service, link_id)

    second_down_time = datetime.now().astimezone().isoformat()
    second_pre_fault_fidelity, second_pre_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    if resource_monitor is not None:
        resource_monitor.mark_event("fault_injected_2", timestamp=second_down_time)
    network.configLinkStatus(src_switch, dst_switch, "down")
    second_ground_truth_fault_timestamp = wait_for_ovs_link_state(
        network,
        src_switch,
        dst_switch,
        expected_up=False,
        topology_definition=topology_definition,
        timeout_seconds=min(timeout_seconds, 5.0),
        sleep_seconds=0.05,
    )
    second_post_fault_fidelity, second_post_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    second_down_event = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=timeout_seconds,
        sleep_seconds=sleep_seconds,
        entity_id=link_id,
        not_before_timestamp=second_down_time,
    )
    second_detection_counters = _link_counter_snapshot(service, link_id)
    runtime_metrics = _capture_runtime_metrics(service)

    return [
        ExperimentRecord(
            scenario_name="link_flap_scenario_down_1",
            topology_name=target_metadata["topology_name"],
            target_link=target_metadata["target_link"],
            target_src_city=target_metadata["target_src_city"],
            target_dst_city=target_metadata["target_dst_city"],
            target_distance_km=target_metadata["target_distance_km"],
            fault_injection_timestamp=first_down_time,
            detection_timestamp=first_down_event.timestamp if first_down_event else "",
            recovery_timestamp="",
            detection_delay=compute_delay_seconds(first_down_time, first_down_event.timestamp)
            if first_down_event
            else None,
            recovery_delay=None,
            poll_interval=service.config.polling_interval_seconds,
            notes=f"First LINK_DOWN event in flap sequence for {src_switch}-{dst_switch}.",
            pre_fault_fidelity=pre_fault_fidelity,
            post_fault_fidelity=first_post_fault_fidelity,
            fidelity_truth_source=_first_truth_source(pre_truth_source, first_post_truth_source),
            ground_truth_fault_timestamp=first_ground_truth_fault_timestamp,
            ground_truth_detection_lag=_ground_truth_lag(
                first_ground_truth_fault_timestamp,
                first_down_event.timestamp if first_down_event else "",
            ),
            node_count=runtime_metrics["node_count"],
            link_count=runtime_metrics["link_count"],
            sync_duration_ms=runtime_metrics["sync_duration_ms"],
            api_call_count=runtime_metrics["api_call_count"],
            pre_fault_total_packets=pre_fault_counters.get("total_packets") if pre_fault_counters else None,
            pre_fault_total_bytes=pre_fault_counters.get("total_bytes") if pre_fault_counters else None,
            post_detection_total_packets=first_detection_counters.get("total_packets") if first_detection_counters else None,
            post_detection_total_bytes=first_detection_counters.get("total_bytes") if first_detection_counters else None,
        ),
        ExperimentRecord(
            scenario_name="link_flap_scenario_up_1",
            topology_name=target_metadata["topology_name"],
            target_link=target_metadata["target_link"],
            target_src_city=target_metadata["target_src_city"],
            target_dst_city=target_metadata["target_dst_city"],
            target_distance_km=target_metadata["target_distance_km"],
            fault_injection_timestamp=up_time,
            detection_timestamp="",
            recovery_timestamp=up_event.timestamp if up_event else "",
            detection_delay=None,
            recovery_delay=compute_delay_seconds(up_time, up_event.timestamp) if up_event else None,
            poll_interval=service.config.polling_interval_seconds,
            notes=f"LINK_UP event in flap sequence after restoring {src_switch}-{dst_switch}.",
            pre_fault_fidelity=pre_recovery_fidelity,
            post_recovery_fidelity=post_recovery_fidelity,
            fidelity_truth_source=_first_truth_source(pre_recovery_truth_source, post_recovery_truth_source),
            ground_truth_recovery_timestamp=ground_truth_recovery_timestamp,
            ground_truth_recovery_lag=_ground_truth_lag(
                ground_truth_recovery_timestamp,
                up_event.timestamp if up_event else "",
            ),
            node_count=runtime_metrics["node_count"],
            link_count=runtime_metrics["link_count"],
            sync_duration_ms=runtime_metrics["sync_duration_ms"],
            api_call_count=runtime_metrics["api_call_count"],
            pre_fault_total_packets=first_detection_counters.get("total_packets") if first_detection_counters else None,
            pre_fault_total_bytes=first_detection_counters.get("total_bytes") if first_detection_counters else None,
            post_recovery_total_packets=post_recovery_counters.get("total_packets") if post_recovery_counters else None,
            post_recovery_total_bytes=post_recovery_counters.get("total_bytes") if post_recovery_counters else None,
        ),
        ExperimentRecord(
            scenario_name="link_flap_scenario_down_2",
            topology_name=target_metadata["topology_name"],
            target_link=target_metadata["target_link"],
            target_src_city=target_metadata["target_src_city"],
            target_dst_city=target_metadata["target_dst_city"],
            target_distance_km=target_metadata["target_distance_km"],
            fault_injection_timestamp=second_down_time,
            detection_timestamp=second_down_event.timestamp if second_down_event else "",
            recovery_timestamp="",
            detection_delay=compute_delay_seconds(second_down_time, second_down_event.timestamp)
            if second_down_event
            else None,
            recovery_delay=None,
            poll_interval=service.config.polling_interval_seconds,
            notes=f"Second LINK_DOWN event in flap sequence for {src_switch}-{dst_switch}.",
            pre_fault_fidelity=second_pre_fault_fidelity,
            post_fault_fidelity=second_post_fault_fidelity,
            fidelity_truth_source=_first_truth_source(second_pre_truth_source, second_post_truth_source),
            ground_truth_fault_timestamp=second_ground_truth_fault_timestamp,
            ground_truth_detection_lag=_ground_truth_lag(
                second_ground_truth_fault_timestamp,
                second_down_event.timestamp if second_down_event else "",
            ),
            node_count=runtime_metrics["node_count"],
            link_count=runtime_metrics["link_count"],
            sync_duration_ms=runtime_metrics["sync_duration_ms"],
            api_call_count=runtime_metrics["api_call_count"],
            pre_fault_total_packets=post_recovery_counters.get("total_packets") if post_recovery_counters else None,
            pre_fault_total_bytes=post_recovery_counters.get("total_bytes") if post_recovery_counters else None,
            post_detection_total_packets=second_detection_counters.get("total_packets") if second_detection_counters else None,
            post_detection_total_bytes=second_detection_counters.get("total_bytes") if second_detection_counters else None,
        ),
    ]


def _run_observation_degradation_runtime(
    service: TwinService,
    network,
    src_switch: str = "s1",
    dst_switch: str = "s2",
    topology_definition: TopologyDefinition | None = None,
    timeout_seconds: float = 20.0,
    resource_monitor: ResourceMonitor | None = None,
) -> ExperimentRecord:
    _wait_for_initial_state(service, timeout_seconds=_initialization_timeout(service, timeout_seconds), sleep_seconds=0.1)
    link_id = _link_id_for_pair(service, src_switch, dst_switch)
    target_metadata = _target_metadata(topology_definition, src_switch, dst_switch)
    pre_fault_fidelity, pre_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    pre_fault_counters = _link_counter_snapshot(service, link_id)

    observation_time = datetime.now().astimezone().isoformat()
    if resource_monitor is not None:
        resource_monitor.mark_event("observation_degradation_injected", timestamp=observation_time)
    sleep_seconds = min(service.config.polling_interval_seconds / 4, 0.5)
    sync_error_event = _wait_for_event(
        service=service,
        event_type="SYNC_ERROR",
        timeout_seconds=timeout_seconds,
        sleep_seconds=sleep_seconds,
        entity_id="/v1.0/topology/links",
        not_before_timestamp=observation_time,
    )
    unexpected_link_down = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=max(service.config.polling_interval_seconds * 1.25, 0.1),
        sleep_seconds=sleep_seconds,
        entity_id=link_id,
        not_before_timestamp=observation_time,
    )

    detection_timestamp = sync_error_event.timestamp if sync_error_event is not None else ""
    detection_delay = (
        compute_delay_seconds(observation_time, detection_timestamp) if detection_timestamp else None
    )
    post_fault_fidelity, post_truth_source = _capture_fidelity_score(
        service,
        network=network,
        topology_definition=topology_definition,
    )
    post_detection_counters = _link_counter_snapshot(service, link_id)
    runtime_metrics = _capture_runtime_metrics(service)

    return ExperimentRecord(
        scenario_name="observation_degradation_scenario",
        topology_name=target_metadata["topology_name"],
        target_link=target_metadata["target_link"],
        target_src_city=target_metadata["target_src_city"],
        target_dst_city=target_metadata["target_dst_city"],
        target_distance_km=target_metadata["target_distance_km"],
        fault_injection_timestamp=observation_time,
        detection_timestamp=detection_timestamp,
        recovery_timestamp="",
        detection_delay=detection_delay,
        recovery_delay=None,
        poll_interval=service.config.polling_interval_seconds,
        notes=(
            "Expected one SYNC_ERROR for /v1.0/topology/links without a matching LINK_DOWN event. "
            f"Observed link_down={unexpected_link_down is not None}."
        ),
        pre_fault_fidelity=pre_fault_fidelity,
        post_fault_fidelity=post_fault_fidelity,
        fidelity_truth_source=_first_truth_source(pre_truth_source, post_truth_source),
        node_count=runtime_metrics["node_count"],
        link_count=runtime_metrics["link_count"],
        sync_duration_ms=runtime_metrics["sync_duration_ms"],
        api_call_count=runtime_metrics["api_call_count"],
        pre_fault_total_packets=pre_fault_counters.get("total_packets") if pre_fault_counters else None,
        pre_fault_total_bytes=pre_fault_counters.get("total_bytes") if pre_fault_counters else None,
        post_detection_total_packets=post_detection_counters.get("total_packets") if post_detection_counters else None,
        post_detection_total_bytes=post_detection_counters.get("total_bytes") if post_detection_counters else None,
    )


def _run_scenario_once(
    scenario_name: str,
    app_config: AppConfig,
    topology_definition: TopologyDefinition | None,
    topology_file: Path | None,
    traffic_config: BackgroundTrafficConfig,
    repeat_index: int,
    configured_repeat_count: int,
    resource_log_path: Path | None = None,
) -> list[ExperimentRecord]:
    """Run one isolated experiment iteration."""

    use_tc = os.getenv("MININET_USE_TC", "true").lower() != "false"
    app_config.events_log_path.write_text("", encoding="utf-8")
    app_config.event_stream_path.write_text("", encoding="utf-8")

    service_client: RyuAPIClient | FaultInjectingRyuClient | None = None
    if scenario_name == "observation_degradation_scenario":
        service_client = FaultInjectingRyuClient(
            RyuAPIClient(base_url=app_config.ryu_base_url),
            degraded_attempts={2},
        )
    service = TwinService(app_config, client=service_client, topology_definition=topology_definition)

    if topology_file is None:
        from src.topology.minimal_topology import MinimalTopologyConfig, build_network

        network = build_network(
            MinimalTopologyConfig(
                controller_host=app_config.controller_host,
                controller_port=app_config.controller_port,
                auto_pingall=False,
                drop_into_cli=False,
                use_tc=use_tc,
            )
        )
    else:
        from src.topology.data_driven_topology import DataDrivenTopologyConfig, build_network

        network = build_network(
            DataDrivenTopologyConfig(
                topology_path=topology_file,
                controller_host=app_config.controller_host,
                controller_port=app_config.controller_port,
                auto_pingall=False,
                drop_into_cli=False,
                use_tc=use_tc,
            ),
            definition=topology_definition,
        )

    records: list[ExperimentRecord]
    traffic_session = BackgroundTrafficSession(processes=[], flow_count=0)
    resource_monitor: ResourceMonitor | None = None
    if resource_log_path is not None:
        resource_monitor = ResourceMonitor(
            resource_log_path,
            build_default_process_specs(controller_app=app_config.controller_app),
            interval=0.1,
            base_metadata={
                "scenario_name": scenario_name,
                "background_traffic": traffic_config.profile,
                "background_load_percent": traffic_config.load_percent or "",
                "repeat_index": repeat_index,
            },
        )
        resource_monitor.start()
    network.start()
    try:
        service.start()
        if resource_monitor is not None:
            resource_monitor.mark_event("service_started")
        _wait_for_initial_state(service, timeout_seconds=app_config.initialization_timeout_seconds, sleep_seconds=0.1)
        time.sleep(2.0)
        network.pingAll()
        if resource_monitor is not None:
            resource_monitor.mark_event("pingall_completed")
        traffic_session = _start_background_traffic(network, topology_definition, traffic_config)
        if traffic_session.flow_count:
            time.sleep(1.0)
            if resource_monitor is not None:
                resource_monitor.mark_event("background_traffic_started")
        if scenario_name == "single_link_failure":
            src_switch, dst_switch = _scenario_link_targets(scenario_name, topology_definition)[0]
            records = [
                _run_single_link_failure_runtime(
                    service,
                    network,
                    src_switch=src_switch,
                    dst_switch=dst_switch,
                    topology_definition=topology_definition,
                    timeout_seconds=app_config.scenario_timeout_seconds,
                    resource_monitor=resource_monitor,
                )
            ]
        elif scenario_name == "recovery_scenario":
            src_switch, dst_switch = _scenario_link_targets(scenario_name, topology_definition)[0]
            records = [
                _run_recovery_runtime(
                    service,
                    network,
                    src_switch=src_switch,
                    dst_switch=dst_switch,
                    topology_definition=topology_definition,
                    timeout_seconds=app_config.scenario_timeout_seconds,
                    resource_monitor=resource_monitor,
                )
            ]
        elif scenario_name == "multi_fault_scenario":
            first_target, second_target = _scenario_link_targets(scenario_name, topology_definition)
            records = _run_multi_fault_runtime(
                service,
                network,
                first_target=first_target,
                second_target=second_target,
                topology_definition=topology_definition,
                timeout_seconds=app_config.scenario_timeout_seconds,
                resource_monitor=resource_monitor,
            )
        elif scenario_name == "link_flap_scenario":
            src_switch, dst_switch = _scenario_link_targets(scenario_name, topology_definition)[0]
            records = _run_link_flap_runtime(
                service,
                network,
                src_switch=src_switch,
                dst_switch=dst_switch,
                topology_definition=topology_definition,
                timeout_seconds=app_config.scenario_timeout_seconds,
                resource_monitor=resource_monitor,
            )
        elif scenario_name == "observation_degradation_scenario":
            src_switch, dst_switch = _scenario_link_targets(scenario_name, topology_definition)[0]
            records = [
                _run_observation_degradation_runtime(
                    service,
                    network,
                    src_switch=src_switch,
                    dst_switch=dst_switch,
                    topology_definition=topology_definition,
                    timeout_seconds=app_config.scenario_timeout_seconds,
                    resource_monitor=resource_monitor,
                )
            ]
        else:
            raise ValueError(f"Unsupported scenario: {scenario_name}")
    finally:
        if resource_monitor is not None:
            resource_monitor.mark_event("scenario_teardown")
        traffic_session.stop()
        network.stop()
        service.stop()
        if resource_monitor is not None:
            resource_monitor.stop()

    for record in records:
        controller_queue_metrics = _controller_event_queue_metrics(
            app_config.event_stream_path,
            fault_injection_timestamp=record.fault_injection_timestamp,
            detection_timestamp=record.detection_timestamp,
        )
        record.sync_mode = app_config.sync_mode
        record.background_traffic = traffic_config.profile
        record.background_flow_count = traffic_session.flow_count
        record.background_load_percent = traffic_config.load_percent
        record.background_target_bandwidth_mbps = traffic_config.iperf_bandwidth_mbps
        record.controller_event_queue_depth_at_detection = controller_queue_metrics[
            "controller_event_queue_depth_at_detection"
        ]
        record.controller_event_queue_depth_peak_until_detection = controller_queue_metrics[
            "controller_event_queue_depth_peak_until_detection"
        ]
        record.controller_events_until_detection = controller_queue_metrics["controller_events_until_detection"]
        record.resource_log_file = str(resource_log_path) if resource_log_path is not None else None
        record.repeat_index = repeat_index
        record.configured_repeat_count = configured_repeat_count
        record.controller_app = app_config.controller_app
        if topology_file is not None:
            record.topology_file = str(topology_file)

    return records


def run_scenario(
    scenario_name: str,
    config: AppConfig | None = None,
    csv_path: Path | None = None,
    topology_file: Path | None = None,
    background_traffic: BackgroundTrafficConfig | None = None,
    repeat: int = 1,
) -> list[ExperimentRecord]:
    """Run a named Mininet-backed experiment scenario and export its results."""

    if repeat < 1:
        raise ValueError("repeat must be at least 1")

    app_config = config or AppConfig()
    app_config.ensure_directories()
    traffic_config = background_traffic or BackgroundTrafficConfig()
    topology_definition: TopologyDefinition | None = None

    if topology_file is not None:
        topology_definition = load_topology_definition(topology_file)

    target_csv = csv_path or (app_config.exports_dir / f"{scenario_name}.csv")
    resource_log_path = target_csv.with_name(f"{target_csv.stem}_resource_logs.csv")
    if resource_log_path.exists():
        resource_log_path.unlink()

    records: list[ExperimentRecord] = []
    for repeat_index in range(1, repeat + 1):
        records.extend(
            _run_scenario_once(
                scenario_name=scenario_name,
                app_config=app_config,
                topology_definition=topology_definition,
                topology_file=topology_file,
                traffic_config=traffic_config,
                repeat_index=repeat_index,
                configured_repeat_count=repeat,
                resource_log_path=resource_log_path,
            )
        )

    write_experiment_results(records, target_csv)
    write_experiment_summary(records, target_csv.with_suffix(".json"))
    summary_rows = summarize_experiment_records(records)
    write_experiment_statistics(
        summary_rows,
        target_csv.with_name(f"{target_csv.stem}_summary.csv"),
        target_csv.with_name(f"{target_csv.stem}_summary.json"),
    )
    return records


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the experiment runner."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=[
            "single_link_failure",
            "recovery_scenario",
            "multi_fault_scenario",
            "link_flap_scenario",
            "observation_degradation_scenario",
        ],
        default="recovery_scenario",
    )
    parser.add_argument("--topology-file", type=Path, default=None)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--background-traffic", choices=["none", "icmp", "iperf_tcp"], default="none")
    parser.add_argument("--background-ping-interval", type=float, default=0.2)
    parser.add_argument("--background-load-percent", type=int, default=None)
    parser.add_argument("--iperf-bandwidth-mbps", type=float, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for running one experiment scenario."""

    args = parse_args(argv)
    records = run_scenario(
        args.scenario,
        csv_path=args.output_csv,
        topology_file=args.topology_file,
        background_traffic=BackgroundTrafficConfig(
            profile=args.background_traffic,
            ping_interval_seconds=args.background_ping_interval,
            load_percent=args.background_load_percent,
            iperf_bandwidth_mbps=args.iperf_bandwidth_mbps,
        ),
        repeat=args.repeat,
    )
    print(json.dumps([record.to_row() for record in records], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
