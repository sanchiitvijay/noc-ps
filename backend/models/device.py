"""
Device model — mirrors the ``devices`` table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Device:
    """Representation of a row in the ``devices`` table.

    Attributes:
        device_id: Auto-incremented primary key.
        node_id: Identifier from the upstream monitoring system.
        device_name: Human-readable device name.
        ip_address: IPv4/IPv6 address of the device.
        site_code: Extracted FEI / site code (e.g. ``"0501"``).
        site_name: Human-readable site name (e.g. ``"Lakewood-NJ"``).
        machine_type: Hardware type descriptor.
        vendor: Hardware vendor name.
        location: Free-text location string.
        created_at: Timestamp of row creation.
    """

    device_id: int
    node_id: int | None
    device_name: str
    ip_address: str | None
    site_code: str | None
    site_name: str | None
    machine_type: str | None
    vendor: str | None
    location: str | None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict) -> "Device":
        """Construct a Device from a database row dict."""
        return cls(
            device_id=row["device_id"],
            node_id=row.get("node_id"),
            device_name=row["device_name"],
            ip_address=row.get("ip_address"),
            site_code=row.get("site_code"),
            site_name=row.get("site_name"),
            machine_type=row.get("machine_type"),
            vendor=row.get("vendor"),
            location=row.get("location"),
            created_at=row.get("created_at"),
        )
