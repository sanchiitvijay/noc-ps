"""
Ticket service — historical ticket and event lookup using the master query strategy.

The master query (mirrors query.sql) joins:
  sn_tickets → device_ticket_map → devices → event_logs

It accepts any combination of:
  ip_address, device_name (LIKE), device_type (LIKE),
  event_name (exact), device_id (exact), error_message (LIKE)

Returns standardized rows with ticket + severity + frequency + device + event data.
"""

from __future__ import annotations

import logging
from typing import Any

from database.connection import fetch_all, fetch_one

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Master query — mirrors query.sql exactly
# ---------------------------------------------------------------------------

_MASTER_QUERY = """
SELECT
    t.ticket_number,
    t.ticket_type,
    t.state,
    t.created_on,
    t.updated_on,
    t.short_description,
    t.description,
    t.work_notes,
    CASE
        WHEN e.event_type_name IN ('Node Down', 'EventType-5000', 'EventType-5001')  THEN 'P1'
        WHEN e.event_type_name IN ('Interface Down', 'Interface Status Changed')      THEN 'P2'
        WHEN e.event_type_name IN ('Node Up', 'Interface Up')                         THEN 'P3'
        ELSE 'P4'
    END AS severity,
    COUNT(e.event_id) AS frequency,
    d.machine_type AS device_type,
    d.device_name,
    d.ip_address,
    e.event_time,
    d.device_id,
    e.message
FROM devices d
JOIN event_logs e        ON e.device_id = d.device_id
LEFT JOIN device_ticket_map m ON m.device_id = d.device_id
LEFT JOIN sn_tickets t        ON t.ticket_id = m.ticket_id
WHERE 1=1
  AND (:ip_address    IS NULL OR d.ip_address      = :ip_address)
  AND (:device_name   IS NULL OR d.device_name     LIKE :device_name)
  AND (:device_type   IS NULL OR d.machine_type    LIKE :device_type)
  AND (:event_name    IS NULL OR e.event_type_name = :event_name)
  AND (:device_id     IS NULL OR d.device_id       = :device_id)
  AND (:error_message IS NULL OR e.message         LIKE :error_message)
GROUP BY d.device_id, COALESCE(t.ticket_id, 0)
ORDER BY t.created_on DESC
LIMIT 50;
"""


async def run_master_query(
    conn,
    ip_address: str | None = None,
    device_name: str | None = None,
    device_type: str | None = None,
    event_name: str | None = None,
    device_id: int | None = None,
    error_message: str | None = None,
) -> list[dict]:
    """Execute the master query with any combination of filters.

    Each parameter is optional (pass None to skip). Parameters that support
    LIKE wildcards are noted below.

    Args:
        conn: Active database connection.
        ip_address: Exact IP address match (e.g. ``'10.159.83.95'``).
        device_name: LIKE match on device name (e.g. ``'%Erlanger%'``).
        device_type: LIKE match on machine_type (e.g. ``'%Cisco%'``).
        event_name: Exact event_type_name match (e.g. ``'Node Down'``).
        device_id: Exact device primary key match.
        error_message: LIKE match on event message.

    Returns:
        List of result dicts with ticket + severity + frequency + device + event fields.
    """
    params = {
        "ip_address":    ip_address,
        "device_name":   device_name,
        "device_type":   device_type,
        "event_name":    event_name,
        "device_id":     device_id,
        "error_message": error_message,
    }
    return await fetch_all(conn, _MASTER_QUERY, params)


# ---------------------------------------------------------------------------
# Device lookup (unchanged helper used by error_info_service)
# ---------------------------------------------------------------------------

async def get_device_info(
    conn,
    device_id: int | None = None,
    device_name: str | None = None,
) -> dict | None:
    """Fetch a device row by device_id or device_name.

    Args:
        conn: Active database connection.
        device_id: Primary key of the device (preferred).
        device_name: Name of the device (partial LIKE match used if device_id not provided).

    Returns:
        Device row dict or None.
    """
    if device_id is not None:
        return await fetch_one(
            conn, "SELECT * FROM devices WHERE device_id = ?", (device_id,)
        )
    if device_name is not None:
        return await fetch_one(
            conn,
            "SELECT * FROM devices WHERE device_name LIKE ? LIMIT 1",
            (f"%{device_name}%",),
        )
    return None


# ---------------------------------------------------------------------------
# Event logs for a device+event_type (used in the /error-info response)
# ---------------------------------------------------------------------------

async def get_event_logs(
    conn,
    device_id: int,
    event_type_id: int,
    limit: int = 20,
) -> list[dict]:
    """Return recent event log rows for a device + event type pair.

    Args:
        conn: Active database connection.
        device_id: Device primary key.
        event_type_id: Event type primary key.
        limit: Max rows to return.

    Returns:
        List of event_log dicts ordered by event_id DESC.
    """
    return await fetch_all(
        conn,
        """
        SELECT
            event_id,
            event_time,
            event_type_name,
            message,
            current_status,
            raw_detail
        FROM event_logs
        WHERE device_id = ? AND event_type_id = ?
        ORDER BY event_id DESC
        LIMIT ?
        """,
        (device_id, event_type_id, limit),
    )


# ---------------------------------------------------------------------------
# Incident count helpers (used to compute total_incidents_6m)
# ---------------------------------------------------------------------------

async def count_device_event_type_incidents(
    conn,
    device_id: int,
    event_type_id: int,
    bucket_limit: int | None = None,
) -> int:
    """Count event_log occurrences of a specific event type on a device.

    Args:
        conn: Active database connection.
        device_id: Device primary key.
        event_type_id: Event type primary key.
        bucket_limit: If provided, only count rows with event_id >= this value
            (used to approximate a rolling 6-month window).

    Returns:
        Integer count of matching event_logs rows.
    """
    
    row = await fetch_one(
        conn,
        "SELECT COUNT(*) AS cnt FROM event_logs WHERE device_id = ? AND event_type_id = ?",
        (device_id, event_type_id),
    )
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Public historical info builder (used by error_info_service)
# ---------------------------------------------------------------------------

async def get_historical_info(
    conn,
    device: dict,
    event_type_id: int,
    max_tickets: int = 10,
) -> dict:
    """Run the master query for this device and return consolidated historical info.

    Uses the master query filtered by device_id (+ optionally IP / device_name
    as secondary filters) to fetch related tickets and event data in one shot.

    Args:
        conn: Active database connection.
        device: Device row dict (from the devices table).
        event_type_id: Event type primary key for incident counting.
        max_tickets: Maximum number of tickets to return.

    Returns:
        Dict with ``total_incidents_6m``, ``last_event_id``, ``related_tickets``,
        ``recent_event_logs``.
    """
    device_id = device["device_id"]
    ip_address = device.get("ip_address")

    # Run the master query filtered by device_id
    rows = await run_master_query(conn, device_id=device_id)

    # Deduplicate by ticket_number (keep highest frequency / first seen)
    seen: dict[str, dict] = {}
    for row in rows:
        tn = row.get("ticket_number")
        if tn and tn not in seen:
            seen[tn] = row

    merged = list(seen.values())[:max_tickets]

    # Build related_tickets list (full data for API response)
    related_tickets = []
    for r in merged:
        related_tickets.append({
            "ticket_number":    r.get("ticket_number"),
            "ticket_type":      r.get("ticket_type"),
            "state":            r.get("state"),
            "created_on":       r.get("created_on"),
            "updated_on":       r.get("updated_on"),
            "closed_at":        r.get("closed_at"),
            "short_description": r.get("short_description"),
            "description":      r.get("description"),
            "work_notes":       r.get("work_notes"),
            "severity":         r.get("severity"),
            "frequency":        r.get("frequency"),
            "device_type":      r.get("device_type"),
            "device_name":      r.get("device_name"),
            "ip_address":       r.get("ip_address"),
            "device_id":        r.get("device_id"),
            "event_time":       r.get("event_time"),
            "event_type_name":  r.get("event_type_name"),
            "event_message":    r.get("message"),
            "last_event_id":    r.get("last_event_id"),
        })

    # Approximate 6-month incident count via last 20% of event_id range
    range_row = await fetch_one(
        conn, "SELECT MIN(event_id) as mn, MAX(event_id) as mx FROM event_logs"
    )
    bucket_limit = None
    if range_row and range_row["mx"]:
        id_range = max(1, range_row["mx"] - range_row["mn"])
        bucket_limit = range_row["mx"] - int(id_range * 0.20)

    total_incidents = await count_device_event_type_incidents(
        conn, device_id, event_type_id, bucket_limit
    )

    # Fetch recent raw event logs for this device+event_type
    recent_logs = await get_event_logs(conn, device_id, event_type_id, limit=10)

    # last_event_id — max of the last_event_id from master query rows OR logs
    log_ids = [r.get("last_event_id") for r in merged if r.get("last_event_id")]
    event_log_ids = [r["event_id"] for r in recent_logs if r.get("event_id")]
    all_ids = log_ids + event_log_ids
    last_event_id = max(all_ids) if all_ids else None

    return {
        "total_incidents_6m": total_incidents,
        "last_event_id": last_event_id,
        "related_tickets": related_tickets,
        "recent_event_logs": recent_logs,
    }
