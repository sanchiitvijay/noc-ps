"""
Pydantic schemas for GET /error-info endpoint.

Updated to include:
- Full ticket data (description, work_notes, frequency, severity, event fields)
- Recent raw event logs
- LLM has_ticket_context flag and no_ticket_llm generated_by value
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Sub-schemas
# ---------------------------------------------------------------------------


class DeviceInfo(BaseModel):
    """Basic device information included in the error-info response."""

    device_id: int
    device_name: str
    ip_address: str | None
    site_code: str | None
    site_name: str | None
    machine_type: str | None
    vendor: str | None
    location: str | None


class EventTypeInfo(BaseModel):
    """Event type metadata included in the error-info response."""

    event_type_id: int
    event_type_name: str
    severity: str
    category: str


class RelatedTicket(BaseModel):
    """Full ticket entry (from master query) in the historical_info block."""

    ticket_number: str
    ticket_type: str | None
    state: str | None
    created_on: str | None
    updated_on: str | None
    closed_at: str | None
    short_description: str | None
    description: str | None
    work_notes: str | None

    # Derived from master query
    severity: str | None = None        # P1 / P2 / P3 / P4
    frequency: int | None = None       # event count for this device

    # Device reference fields (from master query join)
    device_type: str | None = None
    device_name: str | None = None
    ip_address: str | None = None
    device_id: int | None = None

    # Event reference fields
    event_time: str | None = None
    event_type_name: str | None = None
    event_message: str | None = None
    last_event_id: int | None = None


class EventLogEntry(BaseModel):
    """A single raw event log row returned in the error-info response."""

    event_id: int
    event_time: str | None
    event_type_name: str | None
    message: str | None
    current_status: int | None
    raw_detail: str | None


class HistoricalInfo(BaseModel):
    """Historical incident summary for a device + event type combination."""

    total_incidents_6m: int            # count of events in ~last 20% id range
    last_event_id: int | None          # highest event_id seen (proxy for recency)
    related_tickets: list[RelatedTicket]
    recent_event_logs: list[EventLogEntry]  # raw error log entries


class PingResult(BaseModel):
    """Result of an ICMP ping check."""

    host: str
    packets_sent: int
    packets_received: int
    packet_loss_pct: float
    avg_rtt_ms: float | None
    reachable: bool


class TracerouteResult(BaseModel):
    """Result of a traceroute check."""

    host: str
    hops: list[dict]   # [{hop: int, host: str, rtt_ms: float|None}]
    completed: bool
    error: str | None = None


class NslookupResult(BaseModel):
    """Result of a DNS lookup check."""

    host: str
    addresses: list[str]
    reverse_lookup: str | None
    error: str | None = None


class PreliminaryChecks(BaseModel):
    """Bundle of network diagnostic results."""

    ping: PingResult
    traceroute: TracerouteResult
    nslookup: NslookupResult


class SuggestedSolution(BaseModel):
    """LLM-generated (or rule-based) analysis and recommended remediation steps.

    ``generated_by`` values:
      - ``"gemini"``        — Gemini LLM with ticket context
      - ``"no_ticket_llm"`` — Gemini LLM but no historical tickets found
      - ``"rule-based"``    — Fallback when LLM is unavailable
    ``has_ticket_context`` tells the frontend whether historical tickets were
    available when the suggestion was produced.
    """

    hypothesis: str
    recommended_steps: list[str]
    confidence: str                 # "high" | "medium" | "low"
    generated_by: str               # "gemini" | "no_ticket_llm" | "rule-based"
    has_ticket_context: bool = True


class ErrorInfoResponse(BaseModel):
    """Full response payload for GET /error-info."""

    success: bool = True
    message: str = "OK"
    data: "ErrorInfoData"


class ErrorInfoData(BaseModel):
    """The main data block within ErrorInfoResponse."""

    device: DeviceInfo
    event_type: EventTypeInfo
    historical_info: HistoricalInfo
    preliminary_checks: PreliminaryChecks
    suggested_solution: SuggestedSolution


# Resolve forward reference
ErrorInfoResponse.model_rebuild()
