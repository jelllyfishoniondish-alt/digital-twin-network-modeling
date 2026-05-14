"""Event generation for state changes and sync failures."""

from __future__ import annotations

from src.twin.models import EventRecord
from src.twin.diff_engine import StateChange


def build_events(changes: list[StateChange], timestamp: str) -> list[EventRecord]:
    """Translate state changes into stable, structured event records."""

    events: list[EventRecord] = []
    for change in changes:
        if change.entity_type == "link" and change.field_name == "is_up":
            if change.old_value in {True} and change.new_value in {False, None}:
                event_type = "LINK_DOWN"
            elif change.old_value in {False, None} and change.new_value is True:
                event_type = "LINK_UP"
            else:
                continue

            events.append(
                EventRecord(
                    timestamp=timestamp,
                    event_type=event_type,
                    entity_type=change.entity_type,
                    entity_id=change.entity_id,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    details=change.details,
                )
            )
        elif change.entity_type == "switch" and change.field_name == "presence":
            if change.old_value is True and change.new_value is False:
                event_type = "SWITCH_DOWN"
            elif change.old_value is False and change.new_value is True:
                event_type = "SWITCH_UP"
            else:
                continue
            events.append(
                EventRecord(
                    timestamp=timestamp,
                    event_type=event_type,
                    entity_type=change.entity_type,
                    entity_id=change.entity_id,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    details=change.details,
                )
            )
        elif change.entity_type == "host":
            if change.field_name == "presence":
                if change.old_value is True and change.new_value is False:
                    event_type = "HOST_LEAVE"
                elif change.old_value is False and change.new_value is True:
                    event_type = "HOST_JOIN"
                else:
                    continue
            elif change.field_name in {"attached_switch", "attached_port"}:
                event_type = "HOST_MIGRATE"
            else:
                continue
            events.append(
                EventRecord(
                    timestamp=timestamp,
                    event_type=event_type,
                    entity_type=change.entity_type,
                    entity_id=change.entity_id,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    details=change.details,
                )
            )
    return events


def build_sync_error_events(errors: list[dict[str, str]], timestamp: str) -> list[EventRecord]:
    """Translate fetch failures into `SYNC_ERROR` events."""

    return [
        EventRecord(
            timestamp=timestamp,
            event_type="SYNC_ERROR",
            entity_type="ryu_api",
            entity_id=error.get("endpoint", "unknown-endpoint"),
            old_value=None,
            new_value=None,
            details={"message": error.get("message", "")},
        )
        for error in errors
    ]
