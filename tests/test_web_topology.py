"""Tests for the topology visualization page."""

from src.web.app import create_app


class StubService:
    def health(self):
        return {"running": False, "has_state": True, "last_sync_timestamp": None, "last_error_count": 0}

    def get_state(self):
        return {"timestamp": "2026-04-01T12:00:00+00:00", "switches": [], "links": [], "hosts": []}

    def get_topology(self):
        return {
            "timestamp": "2026-04-01T12:00:00+00:00",
            "switches": [],
            "links": [],
            "hosts": [],
        }

    def get_events(self, limit=20):
        return []

    def get_fidelity(self):
        return {
            "timestamp": "2026-04-01T12:00:03+00:00",
            "topology_accuracy": 1.0,
            "link_state_accuracy": 1.0,
            "port_counter_drift": {},
            "state_staleness_ms": 0.0,
            "overall_fidelity": 1.0,
        }


def test_topology_page_contains_vis_network_markup() -> None:
    app = create_app(service=StubService())
    client = app.test_client()

    response = client.get("/topology")

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "vis-network" in body
    assert "/api/topology" in body
