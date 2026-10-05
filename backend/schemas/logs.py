"""
Pydantic schemas for GET /get-logs endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EventLogEntry(BaseModel):
    """A single enriched event log row returned in the paginated list."""

    event_id: int
    event_time: str | None
    event_type_id: int | None
    event_type_name: str | None
    severity: str | None
    category: str | None
    message: str | None
    device_id: int | None
    device_name: str | None
    ip_address: str | None
    site_code: str | None
    current_status: int | None
    raw_detail: str | None


class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses."""

    total: int
    page: int
    page_size: int
    total_pages: int


class LogsResponse(BaseModel):
    """Paginated response for GET /get-logs."""

    success: bool = True
    data: list[EventLogEntry]
    message: str = "OK"
    meta: PaginationMeta


class ActivityLogEntry(BaseModel):
    """A single activity log row for admin views."""

    id: int
    user_id: int | None
    username: str | None  # joined from users table
    action: str
    endpoint: str
    ip_address: str | None
    request_body: str | None
    response_status: int | None
    created_at: str | None


class ActivityLogCreate(BaseModel):
    """Request body for manually creating an activity log entry (admin).

    Attributes:
        action: Description of the action taken.
        endpoint: Target endpoint path.
        ip_address: Optional originating IP.
        request_body: Optional JSON payload string.
        response_status: HTTP status code to record.
    """

    action: str = Field(..., min_length=1, max_length=200)
    endpoint: str = Field(..., min_length=1, max_length=500)
    ip_address: str | None = None
    request_body: str | None = None
    response_status: int | None = None


class ActivityLogsResponse(BaseModel):
    """Paginated response for GET /admin/activity-log."""

    success: bool = True
    data: list[ActivityLogEntry]
    message: str = "OK"
    meta: PaginationMeta
