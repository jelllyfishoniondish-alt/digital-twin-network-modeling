"""Tests for building structured state from Ryu payloads and generating events."""

import json
from pathlib import Path

from src.controller.ryu_api_client import RyuAPIClient
from src.topology.topology_loader import load_topology_definition
from src.twin.storage import InMemoryStateStore, JsonLineEventStore
from src.twin.sync_engine import SyncEngine


def test_sync_once_builds_network_state(tmp_path) -> None:
    responses = {
        "http://127.0.0.1:8080/v1.0/topology/switches": [
            {
                "dpid": "0000000000000001",
                "name": "s1",
                "ports": [{"port_no": 1}, {"port_no": 2}],
            },
            {
                "dpid": "0000000000000002",
                "name": "s2",
                "ports": [{"port_no": 1}, {"port_no": 2}],
            },
        ],
        "http://127.0.0.1:8080/v1.0/topology/links": [
            {
                "src": {"dpid": "0000000000000001", "port_no": 2},
                "dst": {"dpid": "0000000000000002", "port_no": 1},
            }
        ],
        "http://127.0.0.1:8080/v1.0/topology/hosts": [
            {
                "mac": "00:00:00:00:00:01",
                "ipv4": ["10.0.0.1/24"],
                "port": {"dpid": "0000000000000001", "port_no": 1},
            }
        ],
        "http://127.0.0.1:8080/stats/switches": [1, 2],
        "http://127.0.0.1:8080/stats/portdesc/1": {
            "1": [{"port_no": 1, "state": 0, "config": 0}, {"port_no": 2, "state": 0, "config": 0}]
        },
        "http://127.0.0.1:8080/stats/portdesc/2": {
            "2": [{"port_no": 1, "state": 0, "config": 0}, {"port_no": 2, "state": 0, "config": 0}]
        },
        "http://127.0.0.1:8080/stats/port/1": {
            "1": [{"port_no": 1, "rx_packets": 10, "tx_packets": 11}, {"port_no": 2, "rx_packets": 20, "tx_packets": 21}]
        },
        "http://127.0.0.1:8080/stats/port/2": {
            "2": [{"port_no": 1, "rx_packets": 30, "tx_packets": 31}, {"port_no": 2, "rx_packets": 40, "tx_packets": 41}]
        },
        "http://127.0.0.1:8080/stats/flow/1": {"1": [{"match": {}}, {"match": {}}]},
        "http://127.0.0.1:8080/stats/flow/2": {"2": [{"match": {}}]},
    }

    client = RyuAPIClient(
        base_url="http://127.0.0.1:8080",
        fetcher=lambda url, timeout: responses[url],
    )
    engine = SyncEngine(client=client, state_store=InMemoryStateStore())

    result = engine.sync_once()

    assert len(result.state.switches) == 2
    assert len(result.state.links) == 1
    assert len(result.state.hosts) == 1
    assert result.state.switches[0].ports[0].rx_packets == 10
    assert result.state.switches[0].flow_count == 2
    assert result.changes == []
    assert result.events == []
    assert result.errors == []


def test_sync_once_generates_link_down_and_up_events(tmp_path) -> None:
    payloads = [
        {
            "topology_switches": [
                {"dpid": "0000000000000001", "name": "s1", "ports": [{"port_no": 2}]},
                {"dpid": "0000000000000002", "name": "s2", "ports": [{"port_no": 1}]},
            ],
            "links": [
                {
                    "src": {"dpid": "0000000000000001", "port_no": 2},
                    "dst": {"dpid": "0000000000000002", "port_no": 1},
                }
            ],
            "hosts": [],
            "port_descriptions": {},
            "port_stats": {},
            "flows": {},
            "errors": [],
        },
        {
            "topology_switches": [
                {"dpid": "0000000000000001", "name": "s1", "ports": [{"port_no": 2}]},
                {"dpid": "0000000000000002", "name": "s2", "ports": [{"port_no": 1}]},
            ],
            "links": [],
            "hosts": [],
            "port_descriptions": {},
            "port_stats": {},
            "flows": {},
            "errors": [],
        },
        {
            "topology_switches": [
                {"dpid": "0000000000000001", "name": "s1", "ports": [{"port_no": 2}]},
                {"dpid": "0000000000000002", "name": "s2", "ports": [{"port_no": 1}]},
            ],
            "links": [
                {
                    "src": {"dpid": "0000000000000001", "port_no": 2},
                    "dst": {"dpid": "0000000000000002", "port_no": 1},
                }
            ],
            "hosts": [],
            "port_descriptions": {},
            "port_stats": {},
            "flows": {},
            "errors": [],
        },
    ]

    class StubClient:
        def __init__(self, items):
            self.items = items
            self.index = 0

        def collect_state_payload(self):
            payload = self.items[self.index]
            self.index += 1
            return payload

    event_log_path = tmp_path / "events.jsonl"
    engine = SyncEngine(
        client=StubClient(payloads),
        state_store=InMemoryStateStore(),
        event_store=JsonLineEventStore(event_log_path),
    )

    first = engine.sync_once()
    second = engine.sync_once()
    third = engine.sync_once()

    assert first.events == []
    assert [event.event_type for event in second.events] == ["LINK_DOWN"]
    assert [event.event_type for event in third.events] == ["LINK_UP"]

    lines = event_log_path.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(line) for line in lines]
    assert [record["event_type"] for record in records] == ["LINK_DOWN", "LINK_UP"]


def test_sync_once_keeps_previous_links_when_link_fetch_fails(tmp_path) -> None:
    payloads = [
        {
            "topology_switches": [
                {"dpid": "0000000000000001", "name": "s1", "ports": [{"port_no": 2}]},
                {"dpid": "0000000000000002", "name": "s2", "ports": [{"port_no": 1}]},
            ],
            "links": [
                {
                    "src": {"dpid": "0000000000000001", "port_no": 2},
                    "dst": {"dpid": "0000000000000002", "port_no": 1},
                }
            ],
            "hosts": [],
            "port_descriptions": {},
            "port_stats": {},
            "flows": {},
            "fetch_status": {"topology_switches": True, "links": True},
            "errors": [],
        },
        {
            "topology_switches": [
                {"dpid": "0000000000000001", "name": "s1", "ports": [{"port_no": 2}]},
                {"dpid": "0000000000000002", "name": "s2", "ports": [{"port_no": 1}]},
            ],
            "links": [],
            "hosts": [],
            "port_descriptions": {},
            "port_stats": {},
            "flows": {},
            "fetch_status": {"topology_switches": True, "links": False},
            "errors": [{"endpoint": "/v1.0/topology/links", "message": "boom"}],
        },
    ]

    class StubClient:
        def __init__(self, items):
            self.items = items
            self.index = 0

        def collect_state_payload(self):
            payload = self.items[self.index]
            self.index += 1
            return payload

    event_log_path = tmp_path / "events.jsonl"
    engine = SyncEngine(
        client=StubClient(payloads),
        state_store=InMemoryStateStore(),
        event_store=JsonLineEventStore(event_log_path),
    )

    first = engine.sync_once()
    second = engine.sync_once()

    assert len(first.state.links) == 1
    assert len(second.state.links) == 1
    assert second.state.links[0].is_up is True
    assert [event.event_type for event in second.events] == ["SYNC_ERROR"]


def test_sync_once_parses_port_flags_from_string_bitmasks() -> None:
    responses = {
        "http://127.0.0.1:8080/v1.0/topology/switches": [
            {"dpid": "0000000000000001", "name": "s1", "ports": [{"port_no": 1}, {"port_no": 2}]}
        ],
        "http://127.0.0.1:8080/v1.0/topology/links": [],
        "http://127.0.0.1:8080/v1.0/topology/hosts": [],
        "http://127.0.0.1:8080/stats/switches": [1],
        "http://127.0.0.1:8080/stats/portdesc/1": {
            "1": [{"port_no": 1, "state": "0", "config": "0"}, {"port_no": 2, "state": "0x1", "config": "0"}]
        },
        "http://127.0.0.1:8080/stats/port/1": {
            "1": [{"port_no": 1, "rx_packets": 10, "tx_packets": 20}, {"port_no": 2, "rx_packets": 11, "tx_packets": 21}]
        },
        "http://127.0.0.1:8080/stats/flow/1": {"1": []},
    }

    client = RyuAPIClient(
        base_url="http://127.0.0.1:8080",
        fetcher=lambda url, timeout: responses[url],
    )
    engine = SyncEngine(client=client, state_store=InMemoryStateStore())

    result = engine.sync_once()

    assert [port.is_up for port in result.state.switches[0].ports] == [True, False]


def test_sync_once_enriches_state_with_topology_metadata() -> None:
    responses = {
        "http://127.0.0.1:8080/v1.0/topology/switches": [
            {"dpid": "0000000000000002", "name": "0000000000000002", "ports": [{"port_no": 1}, {"port_no": 2}]},
            {"dpid": "0000000000000004", "name": "0000000000000004", "ports": [{"port_no": 1}, {"port_no": 2}]},
        ],
        "http://127.0.0.1:8080/v1.0/topology/links": [
            {
                "src": {"dpid": "0000000000000002", "port_no": 2},
                "dst": {"dpid": "0000000000000004", "port_no": 1},
            }
        ],
        "http://127.0.0.1:8080/v1.0/topology/hosts": [],
        "http://127.0.0.1:8080/stats/switches": [2, 4],
        "http://127.0.0.1:8080/stats/portdesc/2": {
            "2": [{"port_no": 1, "state": 0, "config": 0}, {"port_no": 2, "state": 0, "config": 0}]
        },
        "http://127.0.0.1:8080/stats/portdesc/4": {
            "4": [{"port_no": 1, "state": 0, "config": 0}, {"port_no": 2, "state": 0, "config": 0}]
        },
        "http://127.0.0.1:8080/stats/port/2": {"2": [{"port_no": 1, "rx_packets": 10, "tx_packets": 11}]},
        "http://127.0.0.1:8080/stats/port/4": {"4": [{"port_no": 1, "rx_packets": 30, "tx_packets": 31}]},
        "http://127.0.0.1:8080/stats/flow/2": {"2": []},
        "http://127.0.0.1:8080/stats/flow/4": {"4": []},
    }

    topology_definition = load_topology_definition(Path("data/topologies/geant_subset.json"))
    client = RyuAPIClient(
        base_url="http://127.0.0.1:8080",
        fetcher=lambda url, timeout: responses[url],
    )
    engine = SyncEngine(
        client=client,
        state_store=InMemoryStateStore(),
        topology_definition=topology_definition,
    )

    result = engine.sync_once()

    assert result.state.switches[0].country == "FR"
    assert result.state.switches[0].latitude == 48.8566
    assert result.state.links[0].label == "Paris-Frankfurt"
    assert result.state.links[0].distance_km == 478.0
    assert result.state.links[0].bandwidth_mbps == 100
    assert result.state.links[0].latency_ms == 9.0
