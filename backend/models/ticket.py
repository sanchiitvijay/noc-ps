"""
Ticket and DeviceTicketMap models — mirror ``sn_tickets`` and ``device_ticket_map`` tables.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Ticket:
    """Representation of a row in the ``sn_tickets`` table.

    Attributes:
        ticket_id: Auto-incremented primary key.
        ticket_number: Unique ServiceNow ticket number (e.g. ``"INC0012345"``).
        ticket_type: One of INC / RITM / TASK / CHG.
        state: Current ticket state string.
        created_on: Original creation timestamp string (MM-DD-YYYY HH:MM).
        updated_on: Last update timestamp string.
        closed_at: Closure timestamp string.
        assignment_group: Team assigned to this ticket.
        short_description: One-line summary.
        description: Full ticket body.
        work_notes: Accumulated work notes.
        extracted_site_codes: JSON array of FEI codes mentioned in the ticket.
        extracted_ips: JSON array of IP addresses mentioned in the ticket.
        extracted_device_names: JSON array of device names mentioned.
    """

    ticket_id: int
    ticket_number: str
    ticket_type: str | None
    state: str | None
    created_on: str | None
    updated_on: str | None
    closed_at: str | None
    assignment_group: str | None
    short_description: str | None
    description: str | None
    work_notes: str | None
    extracted_site_codes: str | None  # stored as JSON text
    extracted_ips: str | None          # stored as JSON text
    extracted_device_names: str | None # stored as JSON text

    @classmethod
    def from_row(cls, row: dict) -> "Ticket":
        """Construct a Ticket from a database row dict."""
        return cls(
            ticket_id=row["ticket_id"],
            ticket_number=row["ticket_number"],
            ticket_type=row.get("ticket_type"),
            state=row.get("state"),
            created_on=row.get("created_on"),
            updated_on=row.get("updated_on"),
            closed_at=row.get("closed_at"),
            assignment_group=row.get("assignment_group"),
            short_description=row.get("short_description"),
            description=row.get("description"),
            work_notes=row.get("work_notes"),
            extracted_site_codes=row.get("extracted_site_codes"),
            extracted_ips=row.get("extracted_ips"),
            extracted_device_names=row.get("extracted_device_names"),
        )


@dataclass
class DeviceTicketMap:
    """Representation of a row in the ``device_ticket_map`` table.

    Attributes:
        id: Auto-incremented primary key.
        device_id: Foreign key to devices.
        ticket_id: Foreign key to sn_tickets.
        match_type: How the mapping was determined (site_code / device_name / ip_address).
        match_value: The specific value that triggered the match.
        confidence: Score in [0.0, 1.0] indicating match reliability.
    """

    id: int
    device_id: int
    ticket_id: int
    match_type: str
    match_value: str | None
    confidence: float

    @classmethod
    def from_row(cls, row: dict) -> "DeviceTicketMap":
        """Construct a DeviceTicketMap from a database row dict."""
        return cls(
            id=row["id"],
            device_id=row["device_id"],
            ticket_id=row["ticket_id"],
            match_type=row["match_type"],
            match_value=row.get("match_value"),
            confidence=row.get("confidence", 0.5),
        )
