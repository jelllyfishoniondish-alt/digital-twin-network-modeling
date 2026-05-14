"""Storage helpers for state snapshots and event logs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.twin.models import EventRecord, NetworkState


@dataclass(slots=True)
class InMemoryStateStore:
    """Simple in-memory state holder used by the sync engine."""

    current_state: NetworkState | None = None
    history: list[NetworkState] = field(default_factory=list)

    def get_current_state(self) -> NetworkState | None:
        return self.current_state

    def set_current_state(self, state: NetworkState) -> None:
        self.current_state = state
        self.history.append(state)


class JsonSnapshotStore:
    """Persist the latest state snapshot as JSON."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def save(self, state: NetworkState, file_name: str = "current_state.json") -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / file_name
        path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


class JsonLineEventStore:
    """Persist events as JSON Lines for experiment analysis."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append_many(self, events: list[EventRecord]) -> None:
        if not events:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False))
                handle.write("\n")

    def load_recent(self, limit: int = 20) -> list[dict[str, object]]:
        """Load the most recent events from the JSON Lines log."""

        if not self.path.exists():
            return []

        lines = self.path.read_text(encoding="utf-8").splitlines()
        selected = lines[-limit:] if limit > 0 else lines
        return [json.loads(line) for line in selected if line.strip()]
