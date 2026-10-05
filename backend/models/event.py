"""
Event and EventType models — mirror ``event_logs`` and ``event_type_lookup`` tables.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EventType:
    """Representation of a row in the ``event_type_lookup`` table.

    Attributes:
        event_type_id: Primary key.
        event_type_name: Human-readable name.
        severity: One of Critical / Warning / Info / Unknown.
        category: One of connectivity / interface / performance / wireless / power / other.
    """

    event_type_id: int
    event_type_name: str
    severity: str
    category: str

    @classmethod
    def from_row(cls, row: dict) -> "EventType":
        """Construct an EventType from a database row dict."""
        return cls(
            event_type_id=row["event_type_id"],
            event_type_name=row["event_type_name"],
            severity=row["severity"],
            category=row["category"],
        )


@dataclass
class EventLog:
    """Representation of a row in the ``event_logs`` table.

    Attributes:
        event_id: Primary key (also used as a proxy for ordering since
            ``event_time`` contains only HH:MM:SS.mmm without a date).
        event_time: Time-only string e.g. ``"14:03:22.000"``.
        event_type_id: Foreign key to event_type_lookup.
        event_type_name: Denormalized event type name.
        message: Human-readable event message.
        device_id: Foreign key to devices table.
        current_status: Numeric status code from the source system.
        raw_detail: Additional raw detail text from the source.
    """

    event_id: int
    event_time: str | None
    event_type_id: int | None
    event_type_name: str | None
    message: str | None
    device_id: int | None
    current_status: int | None
    raw_detail: str | None

    @classmethod
    def from_row(cls, row: dict) -> "EventLog":
        """Construct an EventLog from a database row dict."""
        return cls(
            event_id=row["event_id"],
            event_time=row.get("event_time"),
            event_type_id=row.get("event_type_id"),
            event_type_name=row.get("event_type_name"),
            message=row.get("message"),
            device_id=row.get("device_id"),
            current_status=row.get("current_status"),
            raw_detail=row.get("raw_detail"),
        )
