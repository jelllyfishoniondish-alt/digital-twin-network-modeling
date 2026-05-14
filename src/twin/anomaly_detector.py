"""Traffic anomaly detection over per-port byte counter deltas."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.twin.models import NetworkState, utc_now_iso


@dataclass(slots=True)
class AnomalyAlert:
    """Structured anomaly record emitted by the traffic anomaly detector."""

    timestamp: str
    alert_type: str
    entity_type: str
    entity_id: str
    metric: str
    current_value: float
    baseline_value: float
    deviation_ratio: float
    severity: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class JsonLineAnomalyStore:
    """Persist anomaly alerts as JSON Lines."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append_many(self, alerts: list[AnomalyAlert]) -> None:
        if not alerts:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for alert in alerts:
                handle.write(json.dumps(alert.to_dict(), ensure_ascii=False))
                handle.write("\n")

    def load_recent(self, limit: int = 20) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        selected = lines[-limit:] if limit > 0 else lines
        return [json.loads(line) for line in selected if line.strip()]


@dataclass(slots=True)
class TrafficAnomalyDetector:
    """Sliding-window anomaly detector for per-port traffic deltas."""

    window_size: int = 10
    stall_mean_threshold: float = 100.0
    history: dict[tuple[str, str], deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def _append_history(self, entity_id: str, metric: str, value: float) -> None:
        series = self.history[(entity_id, metric)]
        series.append(value)
        while len(series) > self.window_size:
            series.popleft()

    def _baseline_stats(self, entity_id: str, metric: str) -> tuple[float, float] | None:
        series = self.history.get((entity_id, metric))
        if series is None or len(series) < 2:
            return None
        values = list(series)
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        return mean_value, variance ** 0.5

    def check(self, current_state: NetworkState, previous_state: NetworkState | None) -> list[AnomalyAlert]:
        """Compare two states and return anomaly alerts for traffic deltas."""

        if previous_state is None:
            return []

        previous_ports = {
            f"{switch.dpid}:{port.port_no}": port
            for switch in previous_state.switches
            for port in switch.ports
        }
        current_ports = {
            f"{switch.dpid}:{port.port_no}": port
            for switch in current_state.switches
            for port in switch.ports
        }

        alerts: list[AnomalyAlert] = []
        for entity_id in sorted(set(current_ports) & set(previous_ports)):
            current_port = current_ports[entity_id]
            previous_port = previous_ports[entity_id]
            for metric in ("rx_bytes", "tx_bytes"):
                current_delta = max(0.0, float(getattr(current_port, metric) - getattr(previous_port, metric)))
                baseline_stats = self._baseline_stats(entity_id, metric)
                if baseline_stats is not None:
                    mean_value, stddev = baseline_stats
                    if current_delta == 0 and mean_value > self.stall_mean_threshold:
                        alerts.append(
                            AnomalyAlert(
                                timestamp=utc_now_iso(),
                                alert_type="COUNTER_STALL",
                                entity_type="port",
                                entity_id=entity_id,
                                metric=metric,
                                current_value=current_delta,
                                baseline_value=mean_value,
                                deviation_ratio=-1.0,
                                severity="critical",
                            )
                        )
                    elif (stddev > 0 and current_delta > mean_value + 2 * stddev) or (
                        stddev == 0 and mean_value > 0 and current_delta > mean_value * 2
                    ):
                        severity = "critical" if current_delta > mean_value + 3 * stddev else "warning"
                        if stddev == 0 and mean_value > 0 and current_delta > mean_value * 3:
                            severity = "critical"
                        alerts.append(
                            AnomalyAlert(
                                timestamp=utc_now_iso(),
                                alert_type="TRAFFIC_SPIKE",
                                entity_type="port",
                                entity_id=entity_id,
                                metric=metric,
                                current_value=current_delta,
                                baseline_value=mean_value,
                                deviation_ratio=(current_delta - mean_value) / max(mean_value, 1.0),
                                severity=severity,
                            )
                        )
                    elif (stddev > 0 and current_delta < max(0.0, mean_value - 2 * stddev)) or (
                        stddev == 0 and mean_value > 0 and current_delta < mean_value * 0.5
                    ):
                        severity = "critical" if current_delta < max(0.0, mean_value - 3 * stddev) else "warning"
                        if stddev == 0 and mean_value > 0 and current_delta < mean_value * 0.25:
                            severity = "critical"
                        alerts.append(
                            AnomalyAlert(
                                timestamp=utc_now_iso(),
                                alert_type="TRAFFIC_DROP",
                                entity_type="port",
                                entity_id=entity_id,
                                metric=metric,
                                current_value=current_delta,
                                baseline_value=mean_value,
                                deviation_ratio=(current_delta - mean_value) / max(mean_value, 1.0),
                                severity=severity,
                            )
                        )
                self._append_history(entity_id, metric, current_delta)

        return alerts
