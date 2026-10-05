"""
ActivityLog model — mirrors the ``activity_logs`` table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ActivityLog:
    """Representation of a row in the ``activity_logs`` table.

    Attributes:
        id: Auto-incremented primary key.
        user_id: Foreign key to users.id (nullable for unauthenticated requests).
        action: HTTP method + path, e.g. ``"POST /auth/login"``.
        endpoint: Raw request path.
        ip_address: Client IP address.
        request_body: JSON-serialised request body (passwords sanitized).
        response_status: HTTP status code of the response.
        created_at: Timestamp the log entry was created.
    """

    id: int
    user_id: int | None
    action: str
    endpoint: str
    ip_address: str | None
    request_body: str | None
    response_status: int | None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict) -> "ActivityLog":
        """Construct an ActivityLog from a database row dict."""
        return cls(
            id=row["id"],
            user_id=row.get("user_id"),
            action=row["action"],
            endpoint=row["endpoint"],
            ip_address=row.get("ip_address"),
            request_body=row.get("request_body"),
            response_status=row.get("response_status"),
            created_at=row.get("created_at"),
        )
