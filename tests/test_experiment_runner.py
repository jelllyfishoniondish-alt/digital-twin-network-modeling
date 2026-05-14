"""Tests for experiment export helpers."""

from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.twin.experiment_runner import (
    ExperimentRecord,
    FaultInjectingRyuClient,
    _background_traffic_pairs,
    _controller_event_queue_metrics,
    _host_endpoints,
    _link_counter_snapshot,
    _link_id_for_pair,
    _run_link_flap_runtime,
    _run_observation_degradation_runtime,
    _scenario_link_targets,
    _target_metadata,
    _topology_is_ready,
    _wait_for_event,
    compute_delay_seconds,
    parse_args,
    summarize_experiment_records,
    write_experiment_results,
)
from src.topology.topology_loader import load_topology_definition


def test_compute_delay_seconds() -> None:
    delay = compute_delay_seconds("2026-04-01T12:00:00+00:00", "2026-04-01T12:00:02.500000+00:00")
    assert delay == 2.5


def test_write_experiment_results(tmp_path) -> None:
    records = [
        ExperimentRecord(
            scenario_name="recovery_scenario",
            fault_injection_timestamp="2026-04-01T12:00:00+00:00",
            detection_timestamp="2026-04-01T12:00:02+00:00",
            recovery_timestamp="2026-04-01T12:00:05+00:00",
            detection_delay=2.0,
            recovery_delay=1.0,
            poll_interval=2.0,
            notes="demo",
        )
    ]

    csv_path = write_experiment_results(records, tmp_path / "result.csv")
    content = csv_path.read_text(encoding="utf-8")

    assert "scenario_name" in content
    assert "recovery_scenario" in content


def test_summarize_experiment_records_groups_repeated_runs() -> None:
    records = [
        ExperimentRecord(
            scenario_name="recovery_scenario",
            fault_injection_timestamp="2026-04-01T12:00:00+00:00",
            detection_timestamp="2026-04-01T12:00:02+00:00",
            recovery_timestamp="2026-04-01T12:00:05+00:00",
            detection_delay=2.0,
            recovery_delay=1.0,
            poll_interval=2.0,
            notes="run-1",
            sync_mode="polling",
            topology_name="geant",
            topology_file="data/topologies/geant.json",
            target_link="Paris-Frankfurt",
            controller_app="src.controller.topology_aware_switch",
            background_traffic="icmp",
            repeat_index=1,
            configured_repeat_count=2,
        ),
        ExperimentRecord(
            scenario_name="recovery_scenario",
            fault_injection_timestamp="2026-04-01T12:10:00+00:00",
            detection_timestamp="2026-04-01T12:10:03+00:00",
            recovery_timestamp="2026-04-01T12:10:06+00:00",
            detection_delay=3.0,
            recovery_delay=2.0,
            poll_interval=2.0,
            notes="run-2",
            sync_mode="polling",
            topology_name="geant",
            topology_file="data/topologies/geant.json",
            target_link="Paris-Frankfurt",
            controller_app="src.controller.topology_aware_switch",
            background_traffic="icmp",
            repeat_index=2,
            configured_repeat_count=2,
        ),
    ]

    summary_rows = summarize_experiment_records(records)

    assert len(summary_rows) == 1
    assert summary_rows[0].samples == 2
    assert summary_rows[0].sync_mode == "polling"
    assert summary_rows[0].topology_file == "data/topologies/geant.json"
    assert summary_rows[0].controller_app == "src.controller.topology_aware_switch"
    assert summary_rows[0].configured_repeat_count == 2
    assert summary_rows[0].detection_mean == 2.5
    assert summary_rows[0].detection_p95 == 2.0
    assert summary_rows[0].recovery_mean == 1.5


def test_summarize_experiment_records_separates_sync_modes() -> None:
    records = [
        ExperimentRecord(
            scenario_name="single_link_failure",
            fault_injection_timestamp="2026-04-01T12:00:00+00:00",
            detection_timestamp="2026-04-01T12:00:01+00:00",
            recovery_timestamp="",
            detection_delay=1.0,
            recovery_delay=None,
            poll_interval=2.0,
            notes="polling",
            sync_mode="polling",
            topology_name="geant",
            target_link="Paris-Frankfurt",
        ),
        ExperimentRecord(
            scenario_name="single_link_failure",
            fault_injection_timestamp="2026-04-01T12:00:00+00:00",
            detection_timestamp="2026-04-01T12:00:02+00:00",
            recovery_timestamp="",
            detection_delay=2.0,
            recovery_delay=None,
            poll_interval=2.0,
            notes="event",
            sync_mode="event_driven",
            topology_name="geant",
            target_link="Paris-Frankfurt",
        ),
    ]

    summary_rows = summarize_experiment_records(records)

    assert len(summary_rows) == 2
    assert [row.sync_mode for row in summary_rows] == ["event_driven", "polling"]


def test_summarize_experiment_records_separates_background_load_levels() -> None:
    records = [
        ExperimentRecord(
            scenario_name="recovery_scenario",
            fault_injection_timestamp="2026-04-01T12:00:00+00:00",
            detection_timestamp="2026-04-01T12:00:01+00:00",
            recovery_timestamp="2026-04-01T12:00:03+00:00",
            detection_delay=1.0,
            recovery_delay=2.0,
            poll_interval=2.0,
            notes="10-percent",
            sync_mode="polling",
            topology_name="geant",
            target_link="Paris-Frankfurt",
            background_traffic="iperf_tcp",
            background_load_percent=10,
            background_target_bandwidth_mbps=10.0,
        ),
        ExperimentRecord(
            scenario_name="recovery_scenario",
            fault_injection_timestamp="2026-04-01T12:10:00+00:00",
            detection_timestamp="2026-04-01T12:10:02+00:00",
            recovery_timestamp="2026-04-01T12:10:05+00:00",
            detection_delay=2.0,
            recovery_delay=3.0,
            poll_interval=2.0,
            notes="30-percent",
            sync_mode="polling",
            topology_name="geant",
            target_link="Paris-Frankfurt",
            background_traffic="iperf_tcp",
            background_load_percent=30,
            background_target_bandwidth_mbps=30.0,
        ),
    ]

    summary_rows = summarize_experiment_records(records)

    assert len(summary_rows) == 2
    assert [row.background_load_percent for row in summary_rows] == [10, 30]


def test_wait_for_event_reads_existing_events_without_forcing_sync() -> None:
    class FakeService:
        def __init__(self):
            self.sync_calls = 0

        def get_events(self, limit=20):
            return [
                {
                    "timestamp": "2026-04-01T12:00:02+00:00",
                    "event_type": "LINK_DOWN",
                    "entity_type": "link",
                    "entity_id": "link-1",
                    "old_value": True,
                    "new_value": False,
                    "details": {},
                }
            ]

        def sync_once(self):
            self.sync_calls += 1
            raise AssertionError("sync_once() should not be called while waiting for background events")

    service = FakeService()

    event = _wait_for_event(
        service=service,
        event_type="LINK_DOWN",
        timeout_seconds=0.01,
        sleep_seconds=0,
        entity_id="link-1",
        not_before_timestamp="2026-04-01T12:00:01+00:00",
    )

    assert event is not None
    assert service.sync_calls == 0


def test_controller_event_queue_metrics_uses_latest_depth_before_detection(tmp_path) -> None:
    stream_path = tmp_path / "controller_events.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-04-01T12:00:00+00:00","event_type":"STATE_CHANGE","queue_depth_after_put":1}',
                '{"timestamp":"2026-04-01T12:00:01+00:00","event_type":"PORT_STATUS","queue_depth_after_put":3}',
                '{"timestamp":"2026-04-01T12:00:02+00:00","event_type":"TOPOLOGY_CHANGE","queue_depth_after_put":2}',
                '{"timestamp":"2026-04-01T12:00:05+00:00","event_type":"PORT_STATUS","queue_depth_after_put":4}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = _controller_event_queue_metrics(
        stream_path,
        fault_injection_timestamp="2026-04-01T12:00:00+00:00",
        detection_timestamp="2026-04-01T12:00:03+00:00",
    )

    assert metrics["controller_event_queue_depth_at_detection"] == 2
    assert metrics["controller_event_queue_depth_peak_until_detection"] == 3
    assert metrics["controller_events_until_detection"] == 3


def test_fault_injecting_ryu_client_marks_link_fetch_failure_on_selected_attempt() -> None:
    class FakeBaseClient:
        def __init__(self) -> None:
            self.calls = 0

        def collect_state_payload(self):
            self.calls += 1
            return {
                "topology_switches": [{"dpid": "0000000000000001"}],
                "links": [{"src": {"dpid": "1"}, "dst": {"dpid": "2"}}],
                "hosts": [],
                "port_descriptions": {},
                "port_stats": {},
                "flows": {},
                "fetch_status": {"links": True},
                "errors": [],
            }

    client = FaultInjectingRyuClient(FakeBaseClient(), degraded_attempts={2})

    first_payload = client.collect_state_payload()
    second_payload = client.collect_state_payload()

    assert first_payload["fetch_status"]["links"] is True
    assert first_payload["links"] != []
    assert second_payload["fetch_status"]["links"] is False
    assert second_payload["links"] == []
    assert second_payload["errors"][-1]["endpoint"] == "/v1.0/topology/links"


def test_link_id_for_pair_resolves_switch_names_to_dpids() -> None:
    service = SimpleNamespace(
        get_state=lambda: {
            "switches": [
                {"name": "s1", "dpid": "0000000000000001"},
                {"name": "s2", "dpid": "0000000000000002"},
            ],
            "links": [
                {
                    "link_id": "0000000000000001:2--0000000000000002:1",
                    "src_dpid": "0000000000000001",
                    "dst_dpid": "0000000000000002",
                }
            ],
        }
    )

    assert _link_id_for_pair(service, "s1", "s2") == "0000000000000001:2--0000000000000002:1"


def test_link_id_for_pair_falls_back_to_mininet_name_pattern() -> None:
    service = SimpleNamespace(
        get_state=lambda: {
            "switches": [
                {"name": "0000000000000001", "dpid": "0000000000000001"},
                {"name": "0000000000000002", "dpid": "0000000000000002"},
            ],
            "links": [
                {
                    "link_id": "0000000000000001:2--0000000000000002:1",
                    "src_dpid": "0000000000000001",
                    "dst_dpid": "0000000000000002",
                }
            ],
        }
    )

    assert _link_id_for_pair(service, "s1", "s2") == "0000000000000001:2--0000000000000002:1"


def test_link_id_for_pair_raises_when_link_is_missing() -> None:
    service = SimpleNamespace(
        get_state=lambda: {
            "switches": [
                {"name": "s1", "dpid": "0000000000000001"},
                {"name": "s2", "dpid": "0000000000000002"},
            ],
            "links": [],
        }
    )

    with pytest.raises(ValueError):
        _link_id_for_pair(service, "s1", "s2")


def test_link_counter_snapshot_aggregates_endpoint_port_counters() -> None:
    service = SimpleNamespace(
        get_state=lambda: {
            "switches": [
                {
                    "dpid": "0000000000000001",
                    "ports": [
                        {"port_no": 2, "rx_packets": 10, "tx_packets": 20, "rx_bytes": 100, "tx_bytes": 200}
                    ],
                },
                {
                    "dpid": "0000000000000002",
                    "ports": [
                        {"port_no": 1, "rx_packets": 30, "tx_packets": 40, "rx_bytes": 300, "tx_bytes": 400}
                    ],
                },
            ],
            "links": [
                {
                    "link_id": "link-1",
                    "src_dpid": "0000000000000001",
                    "dst_dpid": "0000000000000002",
                    "src_port": 2,
                    "dst_port": 1,
                }
            ],
        }
    )

    snapshot = _link_counter_snapshot(service, "link-1")

    assert snapshot == {
        "rx_packets": 40,
        "tx_packets": 60,
        "rx_bytes": 400,
        "tx_bytes": 600,
        "total_packets": 100,
        "total_bytes": 1000,
    }


def test_topology_is_ready_requires_switches_and_links() -> None:
    ready_service = SimpleNamespace(
        get_state=lambda: {
            "switches": [{"name": "s1", "dpid": "0000000000000001"}],
            "links": [{"link_id": "link-1"}],
        }
    )
    empty_service = SimpleNamespace(
        get_state=lambda: {
            "switches": [],
            "links": [],
        }
    )

    assert _topology_is_ready(ready_service) is True
    assert _topology_is_ready(empty_service) is False


def test_scenario_link_targets_uses_topology_definition() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_subset.json"))

    assert _scenario_link_targets("recovery_scenario", definition) == [("s2", "s4")]
    assert _scenario_link_targets("link_flap_scenario", definition) == [("s2", "s4")]
    assert _scenario_link_targets("multi_fault_scenario", definition) == [("s2", "s4"), ("s4", "s5")]


def test_scenario_link_targets_falls_back_to_defaults_when_topology_has_no_override() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_subset.json"))

    assert _scenario_link_targets("observation_degradation_scenario", definition) == [("s1", "s2")]


def test_target_metadata_uses_city_and_link_labels_from_topology_definition() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_subset.json"))

    metadata = _target_metadata(definition, "s2", "s4")

    assert metadata["topology_name"] == "geant_subset"
    assert metadata["target_link"] == "Paris-Frankfurt"
    assert metadata["target_src_city"] == "Paris"
    assert metadata["target_dst_city"] == "Frankfurt"
    assert metadata["target_distance_km"] == 478.0


def test_target_metadata_prefers_city_pair_for_imported_generic_link_labels() -> None:
    definition = load_topology_definition(Path("data/topologies/generated/geant2012_core12.json"))

    metadata = _target_metadata(definition, "s3", "s14")

    assert metadata["topology_name"] == "geant2012_core12"
    assert metadata["target_link"] == "Bulgaria-Greece"
    assert metadata["target_src_city"] == "Bulgaria"
    assert metadata["target_dst_city"] == "Greece"


def test_host_endpoints_use_topology_host_order() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_subset.json"))

    endpoints = _host_endpoints(network=None, topology_definition=definition)

    assert [endpoint.name for endpoint in endpoints[:3]] == ["h1", "h2", "h3"]
    assert endpoints[-1].ip == "10.0.0.8"


def test_background_traffic_pairs_match_outer_hosts_together() -> None:
    definition = load_topology_definition(Path("data/topologies/geant_subset.json"))

    pairs = _background_traffic_pairs(_host_endpoints(network=None, topology_definition=definition))

    assert [(src.name, dst.name) for src, dst in pairs] == [
        ("h1", "h8"),
        ("h2", "h7"),
        ("h3", "h6"),
        ("h4", "h5"),
    ]


def test_run_link_flap_runtime_returns_three_phases() -> None:
    events = [
        {
            "timestamp": "2026-04-01T12:00:01+00:00",
            "event_type": "LINK_DOWN",
            "entity_type": "link",
            "entity_id": "link-1",
            "old_value": True,
            "new_value": False,
            "details": {},
        },
        {
            "timestamp": "2026-04-01T12:00:02+00:00",
            "event_type": "LINK_UP",
            "entity_type": "link",
            "entity_id": "link-1",
            "old_value": False,
            "new_value": True,
            "details": {},
        },
        {
            "timestamp": "2026-04-01T12:00:03+00:00",
            "event_type": "LINK_DOWN",
            "entity_type": "link",
            "entity_id": "link-1",
            "old_value": True,
            "new_value": False,
            "details": {},
        },
    ]

    class FakeService:
        config = SimpleNamespace(polling_interval_seconds=0.1)

        def __init__(self):
            self.event_calls = 0

        def health(self):
            return {"has_state": True}

        def get_state(self):
            return {
                "switches": [
                    {"name": "s1", "dpid": "0000000000000001"},
                    {"name": "s2", "dpid": "0000000000000002"},
                ],
                "links": [
                    {
                        "link_id": "link-1",
                        "src_dpid": "0000000000000001",
                        "dst_dpid": "0000000000000002",
                    }
                ],
            }

        def get_events(self, limit=0):
            current = events[: self.event_calls + 1]
            self.event_calls = min(self.event_calls + 1, len(events) - 1)
            return current

    class FakeNetwork:
        def __init__(self):
            self.actions: list[tuple[str, str, str]] = []

        def configLinkStatus(self, src, dst, status):
            self.actions.append((src, dst, status))

    service = FakeService()
    network = FakeNetwork()

    records = _run_link_flap_runtime(service, network, src_switch="s1", dst_switch="s2", timeout_seconds=0.1)

    assert [record.scenario_name for record in records] == [
        "link_flap_scenario_down_1",
        "link_flap_scenario_up_1",
        "link_flap_scenario_down_2",
    ]
    assert network.actions == [("s1", "s2", "down"), ("s1", "s2", "up"), ("s1", "s2", "down")]


def test_run_observation_degradation_runtime_emits_sync_error_without_link_down() -> None:
    sync_error_timestamp = (datetime.now().astimezone() + timedelta(seconds=1)).isoformat()
    events = [
        {
            "timestamp": sync_error_timestamp,
            "event_type": "SYNC_ERROR",
            "entity_type": "ryu_api",
            "entity_id": "/v1.0/topology/links",
            "old_value": None,
            "new_value": None,
            "details": {"message": "Injected observation degradation for experiment"},
        }
    ]

    class FakeService:
        config = SimpleNamespace(polling_interval_seconds=0.1)

        def health(self):
            return {"has_state": True}

        def get_state(self):
            return {
                "switches": [
                    {"name": "s1", "dpid": "0000000000000001"},
                    {"name": "s2", "dpid": "0000000000000002"},
                ],
                "links": [
                    {
                        "link_id": "link-1",
                        "src_dpid": "0000000000000001",
                        "dst_dpid": "0000000000000002",
                    }
                ],
            }

        def get_events(self, limit=0):
            return events

    class FakeNetwork:
        pass

    record = _run_observation_degradation_runtime(
        FakeService(),
        FakeNetwork(),
        src_switch="s1",
        dst_switch="s2",
        timeout_seconds=0.1,
    )

    assert record.scenario_name == "observation_degradation_scenario"
    assert record.target_link == "s1-s2"
    assert record.detection_timestamp == sync_error_timestamp
    assert record.recovery_delay is None
    assert "Observed link_down=False" in record.notes


def test_parse_args_accepts_topology_file_and_background_traffic() -> None:
    args = parse_args(
        [
            "--scenario",
            "observation_degradation_scenario",
            "--topology-file",
            "data/topologies/geant_subset.json",
            "--background-traffic",
            "iperf_tcp",
            "--background-ping-interval",
            "0.5",
            "--background-load-percent",
            "30",
            "--iperf-bandwidth-mbps",
            "30",
            "--repeat",
            "3",
        ]
    )

    assert args.scenario == "observation_degradation_scenario"
    assert args.topology_file == Path("data/topologies/geant_subset.json")
    assert args.background_traffic == "iperf_tcp"
    assert args.background_ping_interval == 0.5
    assert args.background_load_percent == 30
    assert args.iperf_bandwidth_mbps == 30.0
    assert args.repeat == 3
