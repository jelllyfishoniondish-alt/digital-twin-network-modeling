"""Tests for the traffic anomaly detector."""

from src.twin.anomaly_detector import TrafficAnomalyDetector
from src.twin.models import NetworkState, PortState, SwitchState


def _state(rx_bytes: int, tx_bytes: int) -> NetworkState:
    return NetworkState(
        timestamp="2026-04-01T12:00:00+00:00",
        switches=[
            SwitchState(
                dpid="1",
                name="s1",
                ports=[PortState(port_no=1, rx_bytes=rx_bytes, tx_bytes=tx_bytes)],
            )
        ],
    )


def test_normal_traffic_sequence_produces_no_alerts() -> None:
    detector = TrafficAnomalyDetector(window_size=5)
    previous = _state(0, 0)
    for current_rx in (100, 210, 330, 450, 560):
        current = _state(current_rx, current_rx)
        alerts = detector.check(current, previous)
        previous = current
    assert alerts == []


def test_traffic_spike_produces_alert() -> None:
    detector = TrafficAnomalyDetector(window_size=5)
    previous = _state(0, 0)
    for current_rx in (100, 200, 300, 400, 500):
        current = _state(current_rx, current_rx)
        detector.check(current, previous)
        previous = current

    alerts = detector.check(_state(1500, 1500), previous)

    assert any(alert.alert_type == "TRAFFIC_SPIKE" for alert in alerts)


def test_counter_stall_produces_alert() -> None:
    detector = TrafficAnomalyDetector(window_size=5, stall_mean_threshold=50.0)
    previous = _state(0, 0)
    for current_rx in (100, 200, 300, 400, 500):
        current = _state(current_rx, current_rx)
        detector.check(current, previous)
        previous = current

    alerts = detector.check(_state(500, 500), previous)

    assert any(alert.alert_type == "COUNTER_STALL" for alert in alerts)
