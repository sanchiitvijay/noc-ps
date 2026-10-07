"""
Logs service — paginated queries for event_logs and activity_logs.
"""

from __future__ import annotations

import logging

import aiosqlite

from database.connection import execute_write, fetch_all, fetch_one
from utils.pagination import get_offset, paginate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event logs
# ---------------------------------------------------------------------------


async def get_event_logs(
    conn: aiosqlite.Connection,
    device_id: int | None = None,
    event_type_id: int | None = None,
    severity: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 1000000,
) -> dict:
    """Fetch paginated event_logs with optional filters.

    Joins with ``devices`` and ``event_type_lookup`` to enrich each row.

    Args:
        conn: Active database connection.
        device_id: Filter by specific device.
        event_type_id: Filter by specific event type.
        severity: Filter by severity (P1/P2/P3/P4).
        search: Full-text search in ``message`` or ``raw_detail``.
        page: Page number (1-indexed).
        page_size: Items per page (max enforced by router).

    Returns:
        Dict with ``data`` (list of enriched rows) and ``meta`` (pagination).
    """
    # Build WHERE clause dynamically
    conditions: list[str] = []
    params: list = []

    if device_id is not None:
        conditions.append("el.device_id = ?")
        params.append(device_id)

    if event_type_id is not None:
        conditions.append("el.event_type_id = ?")
        params.append(event_type_id)

    if severity is not None:
        conditions.append("etl.severity = ?")
        params.append(severity)

    if search:
        # Search across message and raw_detail fields
        conditions.append("(el.message LIKE ? OR el.raw_detail LIKE ?)")
        like_term = f"%{search}%"
        params.extend([like_term, like_term])

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    base_query = f"""
        FROM event_logs el
        LEFT JOIN devices d          ON el.device_id     = d.device_id
        LEFT JOIN event_type_lookup etl ON el.event_type_id = etl.event_type_id
        {where_clause}
    """

    # COUNT query for pagination metadata
    count_row = await fetch_one(
        conn, f"SELECT COUNT(*) AS cnt {base_query}", tuple(params)
    )
    total = count_row["cnt"] if count_row else 0

    offset = get_offset(page, page_size)

    # Data query with LIMIT/OFFSET
    rows = await fetch_all(
        conn,
        f"""
        SELECT
            el.event_id,
            el.event_time,
            el.event_type_id,
            el.event_type_name,
            etl.severity,
            etl.category,
            el.message,
            el.device_id,
            d.device_name,
            d.ip_address,
            d.site_code,
            el.current_status,
            el.raw_detail
        {base_query}
        ORDER BY el.event_id DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (page_size, offset),
    )

    return {
        "data": rows,
        "meta": paginate(total, page, page_size),
    }


# ---------------------------------------------------------------------------
# Activity logs
# ---------------------------------------------------------------------------


async def get_activity_logs(
    conn: aiosqlite.Connection,
    page: int = 1,
    page_size: int = 1000000,
) -> dict:
    """Fetch paginated activity_logs, joining username from users table.

    Args:
        conn: Active database connection.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        Dict with ``data`` (list of enriched rows) and ``meta`` (pagination).
    """
    count_row = await fetch_one(conn, "SELECT COUNT(*) AS cnt FROM activity_logs")
    total = count_row["cnt"] if count_row else 0

    offset = get_offset(page, page_size)

    rows = await fetch_all(
        conn,
        """
        SELECT
            al.id,
            al.user_id,
            u.username,
            al.action,
            al.endpoint,
            al.ip_address,
            al.request_body,
            al.response_status,
            al.created_at
        FROM activity_logs al
        LEFT JOIN users u ON al.user_id = u.id
        ORDER BY al.id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )

    return {
        "data": rows,
        "meta": paginate(total, page, page_size),
    }


async def create_activity_log(
    conn: aiosqlite.Connection,
    user_id: int | None,
    action: str,
    endpoint: str,
    ip_address: str | None = None,
    request_body: str | None = None,
    response_status: int | None = None,
) -> int:
    """Insert a new activity log entry.

    Args:
        conn: Active database connection.
        user_id: Foreign key to users (None for unauthenticated).
        action: e.g. ``"POST /auth/login"``
        endpoint: Raw path string.
        ip_address: Client IP.
        request_body: JSON-serialised body (passwords must be sanitized by caller).
        response_status: HTTP status code.

    Returns:
        The new row's primary key id.
    """
    return await execute_write(
        conn,
        """
        INSERT INTO activity_logs
            (user_id, action, endpoint, ip_address, request_body, response_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, action, endpoint, ip_address, request_body, response_status),
    )
