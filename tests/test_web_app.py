"""Tests for the Flask API layer."""

from src.web.app import create_app


class StubService:
    def health(self):
        return {
            "running": False,
            "has_state": True,
            "last_sync_timestamp": "2026-04-01T12:00:00+00:00",
            "last_error_count": 0,
        }

    def get_state(self):
        return {
            "timestamp": "2026-04-01T12:00:00+00:00",
            "switches": [],
            "links": [],
            "hosts": [],
        }

    def get_topology(self):
        return {
            "timestamp": "2026-04-01T12:00:00+00:00",
            "switches": [{"dpid": "1", "name": "s1", "city": None, "flow_count": 0}],
            "links": [{"link_id": "1:2--2:1", "src_dpid": "1", "dst_dpid": "2", "is_up": True}],
            "hosts": [],
        }

    def get_events(self, limit=20):
        return [{"timestamp": "2026-04-01T12:00:02+00:00", "event_type": "LINK_DOWN", "entity_id": "1:2--2:1"}]

    def get_anomalies(self, limit=20):
        return [{"timestamp": "2026-04-01T12:00:04+00:00", "alert_type": "TRAFFIC_SPIKE", "entity_id": "1:1"}]

    def get_fidelity(self):
        return {
            "timestamp": "2026-04-01T12:00:03+00:00",
            "topology_accuracy": 1.0,
            "link_state_accuracy": 1.0,
            "port_counter_drift": {"1:1": 0.0},
            "state_staleness_ms": 10.0,
            "overall_fidelity": 1.0,
        }


def test_web_endpoints_return_expected_payloads() -> None:
    app = create_app(service=StubService())
    client = app.test_client()

    health_response = client.get("/api/health")
    topology_response = client.get("/api/topology")
    events_response = client.get("/api/events")
    anomalies_response = client.get("/api/anomalies")
    state_response = client.get("/api/state")
    fidelity_response = client.get("/api/fidelity")

    assert health_response.status_code == 200
    assert topology_response.json["switches"][0]["name"] == "s1"
    assert events_response.json[0]["event_type"] == "LINK_DOWN"
    assert anomalies_response.json[0]["alert_type"] == "TRAFFIC_SPIKE"
    assert state_response.json["timestamp"] == "2026-04-01T12:00:00+00:00"
    assert fidelity_response.json["overall_fidelity"] == 1.0
