"""Tests for scalability-specific metrics and plotting."""

from src.twin.plotting import build_scalability_plot
from src.twin.sync_engine import SyncEngine
from src.twin.storage import InMemoryStateStore


class StubClient:
    def __init__(self) -> None:
        self.last_api_call_count = 3

    def collect_state_payload(self):
        return {
            "topology_switches": [{"dpid": "1", "ports": [{"port_no": 1}]}],
            "links": [],
            "hosts": [],
            "port_descriptions": {"0000000000000001": {"1": [{"port_no": 1, "state": 0, "config": 0}]}},
            "port_stats": {"0000000000000001": {"1": [{"port_no": 1, "rx_bytes": 1, "tx_bytes": 1}]}},
            "flows": {"0000000000000001": {"1": []}},
            "fetch_status": {"topology_switches": True, "links": True},
            "errors": [],
            "api_call_count": 3,
        }


def test_sync_result_captures_duration() -> None:
    engine = SyncEngine(client=StubClient(), state_store=InMemoryStateStore())

    result = engine.sync_once()

    assert result.sync_duration_ms is not None
    assert result.sync_duration_ms >= 0
    assert result.api_call_count == 3


def test_build_scalability_plot(tmp_path) -> None:
    output_path = build_scalability_plot(
        [
            {"node_count": 3, "detection_delay": 0.5, "sync_duration_ms": 15.0},
            {"node_count": 8, "detection_delay": 1.0, "sync_duration_ms": 32.0},
        ],
        tmp_path / "scalability.png",
    )

    assert output_path.exists()
