"""
IngestJob model — mirrors the ``ingest_jobs`` table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class IngestJob:
    """Representation of a row in the ``ingest_jobs`` table.

    Attributes:
        id: Auto-incremented primary key.
        filename: Original uploaded filename.
        status: Current job status: pending / running / completed / failed.
        started_at: Timestamp when processing began.
        completed_at: Timestamp when processing finished (success or failure).
        rows_processed: Number of rows successfully inserted/updated.
        error_message: Human-readable error description if status=failed.
        triggered_by: User ID of the uploader.
    """

    id: int
    filename: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    rows_processed: int
    error_message: str | None
    triggered_by: int | None

    @classmethod
    def from_row(cls, row: dict) -> "IngestJob":
        """Construct an IngestJob from a database row dict."""
        return cls(
            id=row["id"],
            filename=row["filename"],
            status=row["status"],
            started_at=row.get("started_at"),
            completed_at=row.get("completed_at"),
            rows_processed=row.get("rows_processed", 0),
            error_message=row.get("error_message"),
            triggered_by=row.get("triggered_by"),
        )
