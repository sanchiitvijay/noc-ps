"""
Pydantic schemas for ingest job endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel


class IngestJobResponse(BaseModel):
    """Represents an ingest job record in API responses."""

    id: int
    filename: str
    status: str
    started_at: str | None
    completed_at: str | None
    rows_processed: int
    error_message: str | None
    triggered_by: int | None


class IngestSubmitResponse(BaseModel):
    """Response returned immediately after a file is uploaded.

    The actual processing happens in the background; poll
    ``GET /admin/ingest-excel/{job_id}`` for status updates.
    """

    success: bool = True
    message: str
    data: IngestJobResponse


class IngestStatusResponse(BaseModel):
    """Response for polling the status of an ingest job."""

    success: bool = True
    message: str = "OK"
    data: IngestJobResponse


class DiagnosticRequest(BaseModel):
    """Generic request body for diagnostic endpoints (ping/traceroute/nslookup).

    Attributes:
        host: IP address or hostname to target.
        count: Number of ping packets (ignored by traceroute/nslookup).
    """

    host: str
    count: int = 4
