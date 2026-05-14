"""Tests for the Ryu API client."""

from urllib.error import URLError

from src.controller.ryu_api_client import RyuAPIClient


def test_collect_state_payload() -> None:
    responses = {
        "http://127.0.0.1:8080/v1.0/topology/switches": [
            {
                "dpid": "0000000000000001",
                "name": "s1",
                "ports": [{"port_no": 1}, {"port_no": 2}],
            }
        ],
        "http://127.0.0.1:8080/v1.0/topology/links": [],
        "http://127.0.0.1:8080/v1.0/topology/hosts": [],
        "http://127.0.0.1:8080/stats/switches": [1],
        "http://127.0.0.1:8080/stats/portdesc/1": {
            "1": [{"port_no": 1, "state": 0, "config": 0}]
        },
        "http://127.0.0.1:8080/stats/port/1": {
            "1": [{"port_no": 1, "rx_packets": 10, "tx_packets": 20}]
        },
        "http://127.0.0.1:8080/stats/flow/1": {"1": [{"match": {}}]},
    }

    client = RyuAPIClient(
        base_url="http://127.0.0.1:8080",
        fetcher=lambda url, timeout: responses[url],
    )
    payload = client.collect_state_payload()

    assert payload["topology_switches"][0]["name"] == "s1"
    assert payload["port_stats"]["0000000000000001"]["1"][0]["rx_packets"] == 10
    assert payload["flows"]["0000000000000001"]["1"][0]["match"] == {}
    assert payload["errors"] == []


def test_collect_state_payload_falls_back_to_decimal_switch_ids() -> None:
    responses = {
        "http://127.0.0.1:8080/v1.0/topology/switches": [
            {
                "dpid": "0000000000000001",
                "name": "s1",
                "ports": [{"port_no": 1}],
            }
        ],
        "http://127.0.0.1:8080/v1.0/topology/links": [],
        "http://127.0.0.1:8080/v1.0/topology/hosts": [],
        "http://127.0.0.1:8080/stats/switches": ["0000000000000001"],
        "http://127.0.0.1:8080/stats/portdesc/1": {
            "1": [{"port_no": 1, "state": 0, "config": 0}]
        },
        "http://127.0.0.1:8080/stats/port/1": {
            "1": [{"port_no": 1, "rx_packets": 10, "tx_packets": 20}]
        },
        "http://127.0.0.1:8080/stats/flow/1": {"1": [{"match": {}}]},
    }

    def fetcher(url, timeout):
        if url not in responses:
            raise URLError(f"missing: {url}")
        return responses[url]

    client = RyuAPIClient(base_url="http://127.0.0.1:8080", fetcher=fetcher)
    payload = client.collect_state_payload()

    assert payload["port_descriptions"]["0000000000000001"]["1"][0]["port_no"] == 1
    assert payload["fetch_status"]["port_descriptions"]["0000000000000001"] is True
    assert payload["errors"] == []
