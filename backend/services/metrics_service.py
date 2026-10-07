"""
Metrics service — aggregation queries for the /get-metrics endpoint.

NOTE: event_logs.event_time stores time-only values (HH:MM:SS.mmm) without
a date component. Temporal windows (24h, 7d, 30d) are therefore approximated
by dividing the event_id range into proportional buckets. This limitation is
documented in the API response.
"""

from __future__ import annotations

import logging

import aiosqlite

from database.connection import fetch_all, fetch_one

logger = logging.getLogger(__name__)


async def get_total_events(conn: aiosqlite.Connection) -> dict:
    """Return total event counts across all time and approximate windows.

    Since ``event_time`` has no date, we approximate recent windows by
    slicing the ``event_id`` range proportionally.

    Strategy:
        - all_time: SELECT COUNT(*) FROM event_logs
        - max/min event_id are fetched; the id range is divided into
          fictional windows: last ~4% ≈ 24h, ~23% ≈ 7d, ~100% of 30-day range ≈ 30d

    Args:
        conn: Active database connection.

    Returns:
        Dict with ``all_time``, ``last_24h_approx``, ``last_7d_approx``,
        ``last_30d_approx`` keys.
    """
    total_row = await fetch_one(conn, "SELECT COUNT(*) as cnt FROM event_logs")
    total = total_row["cnt"] if total_row else 0

    # Fetch min/max event_id to partition the range
    range_row = await fetch_one(
        conn, "SELECT MIN(event_id) as mn, MAX(event_id) as mx FROM event_logs"
    )
    if not range_row or range_row["mx"] is None:
        return {
            "all_time": 0,
            "last_24h_approx": 0,
            "last_7d_approx": 0,
            "last_30d_approx": 0,
        }

    mn, mx = range_row["mn"], range_row["mx"]
    id_range = max(1, mx - mn)

    # Proportional buckets — assuming data spans ~30 days total
    cutoff_24h = mx - int(id_range * (1 / 30))
    cutoff_7d = mx - int(id_range * (7 / 30))
    cutoff_30d = mn  # essentially all

    async def _count_from(cutoff: int) -> int:
        row = await fetch_one(
            conn,
            "SELECT COUNT(*) as cnt FROM event_logs WHERE event_id >= ?",
            (cutoff,),
        )
        return row["cnt"] if row else 0

    return {
        "all_time": total,
        "last_24h_approx": await _count_from(cutoff_24h),
        "last_7d_approx": await _count_from(cutoff_7d),
        "last_30d_approx": total,  # all data is within our 30d dataset
    }


async def get_events_by_severity(conn: aiosqlite.Connection) -> dict:
    """Return event counts grouped by severity from event_type_lookup.

    Uses a JOIN between event_logs and event_type_lookup.

    Args:
        conn: Active database connection.

    Returns:
        Dict mapping severity level to count.
    """
    rows = await fetch_all(
        conn,
        """
        SELECT
            etl.severity AS severity,
            COUNT(*)                           AS cnt
        FROM event_logs el
        LEFT JOIN event_type_lookup etl ON el.event_type_id = etl.event_type_id
        GROUP BY etl.severity
        """
    )
    result = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
    for row in rows:
        sev = row["severity"]
        if sev:
            result[sev] = result.get(sev, 0) + row["cnt"]
    return result


async def get_events_by_category(conn: aiosqlite.Connection) -> dict:
    """Return event counts grouped by category from event_type_lookup.

    Args:
        conn: Active database connection.

    Returns:
        Dict mapping category name to count.
    """
    rows = await fetch_all(
        conn,
        """
        SELECT
            COALESCE(etl.category, 'other') AS category,
            COUNT(*)                         AS cnt
        FROM event_logs el
        LEFT JOIN event_type_lookup etl ON el.event_type_id = etl.event_type_id
        GROUP BY etl.category
        """,
    )
    result = {
        "connectivity": 0,
        "interface": 0,
        "performance": 0,
        "wireless": 0,
        "power": 0,
        "other": 0,
    }
    for row in rows:
        cat = row["category"] or "other"
        result[cat] = result.get(cat, 0) + row["cnt"]
    return result


async def get_top_alerting_devices(
    conn: aiosqlite.Connection,
    limit: int = 10,
) -> list[dict]:
    """Return the top N devices by event count.

    Joins event_logs with devices to include device metadata.

    Args:
        conn: Active database connection.
        limit: Maximum number of devices to return.

    Returns:
        List of dicts with ``device_id``, ``device_name``, ``ip_address``,
        ``site_code``, ``event_count``.
    """
    return await fetch_all(
        conn,
        """
        SELECT
            d.device_id,
            d.device_name,
            d.ip_address,
            d.site_code,
            COUNT(el.event_id) AS event_count
        FROM event_logs el
        JOIN devices d ON el.device_id = d.device_id
        GROUP BY el.device_id
        ORDER BY event_count DESC
        LIMIT ?
        """,
        (limit,),
    )


async def get_recent_trend(conn: aiosqlite.Connection, buckets: int = 30) -> list[dict]:
    """Divide the total event_id range into *buckets* and count events per bucket.

    Since ``event_time`` is time-only, we use ``event_id`` range partitioning
    to simulate a temporal trend. Bucket 1 = oldest, bucket N = newest.

    Args:
        conn: Active database connection.
        buckets: Number of trend buckets to return (default 30).

    Returns:
        List of ``{"bucket": int, "event_count": int}`` dicts.
    """
    range_row = await fetch_one(
        conn, "SELECT MIN(event_id) as mn, MAX(event_id) as mx FROM event_logs"
    )
    if not range_row or range_row["mx"] is None:
        return [{"bucket": i + 1, "event_count": 0} for i in range(buckets)]

    mn, mx = range_row["mn"], range_row["mx"]
    id_range = max(1, mx - mn)
    bucket_size = id_range / buckets

    trend = []
    for i in range(buckets):
        lo = mn + int(i * bucket_size)
        hi = mn + int((i + 1) * bucket_size)
        if i == buckets - 1:
            hi = mx + 1  # inclusive of the last id
        row = await fetch_one(
            conn,
            "SELECT COUNT(*) as cnt FROM event_logs WHERE event_id >= ? AND event_id < ?",
            (lo, hi),
        )
        trend.append({"bucket": i + 1, "event_count": row["cnt"] if row else 0})
    return trend


async def get_ticket_stats(conn: aiosqlite.Connection) -> dict:
    """Return summary statistics for ServiceNow tickets.

    Args:
        conn: Active database connection.

    Returns:
        Dict with ``total_tickets``, ``by_state``, ``by_type`` keys.
    """
    total_row = await fetch_one(conn, "SELECT COUNT(*) as cnt FROM sn_tickets")
    total = total_row["cnt"] if total_row else 0

    state_rows = await fetch_all(
        conn,
        "SELECT COALESCE(state, 'Unknown') AS state, COUNT(*) AS cnt FROM sn_tickets GROUP BY state",
    )
    by_state = {r["state"]: r["cnt"] for r in state_rows}

    type_rows = await fetch_all(
        conn,
        "SELECT COALESCE(ticket_type, 'Unknown') AS ticket_type, COUNT(*) AS cnt FROM sn_tickets GROUP BY ticket_type",
    )
    by_type = {r["ticket_type"]: r["cnt"] for r in type_rows}

    return {"total_tickets": total, "by_state": by_state, "by_type": by_type}


async def get_total_devices(conn: aiosqlite.Connection) -> int:
    """Return the total number of devices in the devices table.

    Args:
        conn: Active database connection.

    Returns:
        Integer count of device rows.
    """
    row = await fetch_one(conn, "SELECT COUNT(*) as cnt FROM devices")
    return row["cnt"] if row else 0


async def build_metrics(conn: aiosqlite.Connection) -> dict:
    """Orchestrate all metric queries and return the combined payload.

    Args:
        conn: Active database connection.

    Returns:
        Full metrics dict ready to be serialized as MetricsResponse.
    """
    total_events = await get_total_events(conn)
    events_by_severity = await get_events_by_severity(conn)
    events_by_category = await get_events_by_category(conn)
    top_alerting_devices = await get_top_alerting_devices(conn)
    

    return {
        "total_events": total_events,
        "events_by_severity": events_by_severity,
        "events_by_category": events_by_category,
        "top_alerting_devices": top_alerting_devices,
    }
