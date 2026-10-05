"""
Pydantic schemas for GET /get-metrics endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TotalEvents(BaseModel):
    """Breakdown of event counts across time windows.

    Note:
        ``event_logs.event_time`` contains only a time portion (HH:MM:SS.mmm)
        without a date. The 24h/7d/30d figures are approximations based on
        ``event_id`` range buckets rather than calendar timestamps.
        This limitation is surfaced in the API response via
        ``MetricsResponse.notes``.
    """

    all_time: int
    last_24h_approx: int = Field(
        description="Approximation — derived from event_id bucket, not real timestamps"
    )
    last_7d_approx: int
    last_30d_approx: int


class SeverityBreakdown(BaseModel):
    """Event counts grouped by severity level."""

    Critical: int = 0
    Warning: int = 0
    Info: int = 0
    Unknown: int = 0


class CategoryBreakdown(BaseModel):
    """Event counts grouped by category."""

    connectivity: int = 0
    interface: int = 0
    performance: int = 0
    wireless: int = 0
    power: int = 0
    other: int = 0


class TopAlertingDevice(BaseModel):
    """One device in the top-alerting list."""

    device_id: int
    device_name: str
    ip_address: str | None
    site_code: str | None
    event_count: int


class DailyTrendPoint(BaseModel):
    """A single bucket in the recent event trend.

    Note:
        Buckets are based on ``event_id`` ranges divided evenly over 30 buckets
        because the source data has time-only values. The ``bucket`` field is
        ``1`` (oldest) to ``30`` (newest).
    """

    bucket: int
    event_count: int


class TicketStats(BaseModel):
    """Summary statistics for ServiceNow tickets."""

    total_tickets: int
    by_state: dict[str, int]
    by_type: dict[str, int]


class MetricsResponse(BaseModel):
    """Full metrics payload returned by GET /get-metrics."""

    total_events: TotalEvents
    events_by_severity: SeverityBreakdown
    events_by_category: CategoryBreakdown
    top_alerting_devices: list[TopAlertingDevice]
