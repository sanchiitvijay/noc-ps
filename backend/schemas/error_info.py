"""
Pydantic schemas for GET /error-info endpoint.
"""

from __future__ import annotations

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
    """Summarised ticket entry in the historical_info block."""

    ticket_number: str
    ticket_type: str | None
    state: str | None
    short_description: str | None
    work_notes: str | None
    closed_at: str | None
    confidence: float | None = None
    match_type: str | None = None


class HistoricalInfo(BaseModel):
    """Historical incident summary for a device + event type combination."""

    total_incidents_6m: int  # count of events for this event_type on this device
    last_event_id: int | None  # highest event_id seen (proxy for recency)
    related_tickets: list[RelatedTicket]


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
    hops: list[dict]  # [{hop: int, host: str, rtt_ms: float|None}]
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
    """LLM-generated analysis and recommended remediation steps."""

    hypothesis: str
    recommended_steps: list[str]
    confidence: str  # "high" | "medium" | "low"
    generated_by: str = "gemini"


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
