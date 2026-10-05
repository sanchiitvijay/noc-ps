"""
Ticket service — historical ticket lookup using multiple query strategies.

Implements 4 lookup strategies with fallback and deduplication:
  1. Exact device match via device_ticket_map (highest confidence)
  2. Site code match in sn_tickets.extracted_site_codes JSON
  3. IP address match in sn_tickets.extracted_ips JSON
  4. Fuzzy device name match on extracted_device_names
"""

from __future__ import annotations

import json
import logging

import aiosqlite

from database.connection import fetch_all, fetch_one

logger = logging.getLogger(__name__)


async def get_device_info(
    conn: aiosqlite.Connection,
    device_id: int | None = None,
    device_name: str | None = None,
) -> dict | None:
    """Fetch a device row by device_id or device_name.

    Args:
        conn: Active database connection.
        device_id: Primary key of the device (preferred).
        device_name: Name of the device (used if device_id not provided).

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
# Strategy 1: Exact device_ticket_map lookup
# ---------------------------------------------------------------------------

async def _strategy_direct_map(
    conn: aiosqlite.Connection,
    device_id: int,
) -> list[dict]:
    """Look up tickets directly mapped to the device in device_ticket_map.

    Orders by confidence DESC to surface the best matches first.

    Args:
        conn: Active database connection.
        device_id: The device's primary key.

    Returns:
        List of ticket dicts enriched with confidence and match_type.
    """
    return await fetch_all(
        conn,
        """
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.ticket_type,
            t.state,
            t.created_on,
            t.updated_on,
            t.closed_at,
            t.short_description,
            t.work_notes,
            dtm.match_type,
            dtm.match_value,
            dtm.confidence
        FROM device_ticket_map dtm
        JOIN sn_tickets t ON dtm.ticket_id = t.ticket_id
        WHERE dtm.device_id = ?
        ORDER BY dtm.confidence DESC
        """,
        (device_id,),
    )


# ---------------------------------------------------------------------------
# Strategy 2: Site code match in extracted_site_codes JSON
# ---------------------------------------------------------------------------

async def _strategy_site_code(
    conn: aiosqlite.Connection,
    site_code: str,
) -> list[dict]:
    """Search sn_tickets whose extracted_site_codes contain the given site code.

    The extracted_site_codes column is stored as a JSON array text.
    We use a LIKE search which works correctly for simple 4-digit FEI codes.

    Args:
        conn: Active database connection.
        site_code: FEI site code string (e.g. ``"0501"``).

    Returns:
        List of matching ticket dicts with a synthetic confidence of 0.7.
    """
    rows = await fetch_all(
        conn,
        """
        SELECT
            ticket_id, ticket_number, ticket_type, state,
            created_on, updated_on, closed_at,
            short_description, work_notes
        FROM sn_tickets
        WHERE extracted_site_codes LIKE ?
        """,
        (f'%"{site_code}"%',),  # JSON array contains the code as a quoted string
    )
    for row in rows:
        row["match_type"] = "site_code"
        row["match_value"] = site_code
        row["confidence"] = 0.7
    return rows


# ---------------------------------------------------------------------------
# Strategy 3: IP address match in extracted_ips JSON
# ---------------------------------------------------------------------------

async def _strategy_ip_match(
    conn: aiosqlite.Connection,
    ip_address: str,
) -> list[dict]:
    """Search sn_tickets whose extracted_ips contain the given IP address.

    Args:
        conn: Active database connection.
        ip_address: The device's IP address string.

    Returns:
        List of matching ticket dicts with a synthetic confidence of 0.8.
    """
    rows = await fetch_all(
        conn,
        """
        SELECT
            ticket_id, ticket_number, ticket_type, state,
            created_on, updated_on, closed_at,
            short_description, work_notes
        FROM sn_tickets
        WHERE extracted_ips LIKE ?
        """,
        (f'%"{ip_address}"%',),
    )
    for row in rows:
        row["match_type"] = "ip_address"
        row["match_value"] = ip_address
        row["confidence"] = 0.8
    return rows


# ---------------------------------------------------------------------------
# Strategy 4: Fuzzy device name match on extracted_device_names
# ---------------------------------------------------------------------------

async def _strategy_device_name_fuzzy(
    conn: aiosqlite.Connection,
    device_name: str,
) -> list[dict]:
    """LIKE search on extracted_device_names for partial device name match.

    Strips trailing numeric suffixes to improve match breadth.

    Args:
        conn: Active database connection.
        device_name: Device name string.

    Returns:
        List of matching ticket dicts with a synthetic confidence of 0.5.
    """
    # Use the base device name (strip trailing digits) for broader matching
    base_name = device_name.rstrip("0123456789").strip("-_. ")
    pattern = f"%{base_name}%" if base_name else f"%{device_name}%"

    rows = await fetch_all(
        conn,
        """
        SELECT
            ticket_id, ticket_number, ticket_type, state,
            created_on, updated_on, closed_at,
            short_description, work_notes
        FROM sn_tickets
        WHERE extracted_device_names LIKE ?
        """,
        (pattern,),
    )
    for row in rows:
        row["match_type"] = "device_name"
        row["match_value"] = device_name
        row["confidence"] = 0.5
    return rows


# ---------------------------------------------------------------------------
# Deduplication and merging
# ---------------------------------------------------------------------------

def _merge_and_deduplicate(results: list[list[dict]]) -> list[dict]:
    """Merge results from multiple strategies, keeping the highest-confidence
    entry per ticket_id.

    Args:
        results: List of result lists from each strategy.

    Returns:
        Deduplicated, confidence-sorted list of ticket dicts.
    """
    seen: dict[int, dict] = {}
    for result_set in results:
        for ticket in result_set:
            tid = ticket["ticket_id"]
            if tid not in seen or ticket.get("confidence", 0) > seen[tid].get("confidence", 0):
                seen[tid] = ticket

    # Sort descending by confidence
    return sorted(seen.values(), key=lambda t: t.get("confidence", 0), reverse=True)


# ---------------------------------------------------------------------------
# Count recent incidents
# ---------------------------------------------------------------------------

async def count_device_event_type_incidents(
    conn: aiosqlite.Connection,
    device_id: int,
    event_type_id: int,
    bucket_limit: int | None = None,
) -> int:
    """Count event_log occurrences of a specific event type on a device.

    Since there are no real dates, this counts all matching rows unless
    a rough id-range limit is applied.

    Args:
        conn: Active database connection.
        device_id: Device primary key.
        event_type_id: Event type primary key.
        bucket_limit: If provided, only count rows with event_id >= this value.

    Returns:
        Integer count of matching event_logs rows.
    """
    if bucket_limit is not None:
        row = await fetch_one(
            conn,
            """
            SELECT COUNT(*) AS cnt FROM event_logs
            WHERE device_id = ? AND event_type_id = ? AND event_id >= ?
            """,
            (device_id, event_type_id, bucket_limit),
        )
    else:
        row = await fetch_one(
            conn,
            "SELECT COUNT(*) AS cnt FROM event_logs WHERE device_id = ? AND event_type_id = ?",
            (device_id, event_type_id),
        )
    return row["cnt"] if row else 0


async def get_last_event_id_for_device(
    conn: aiosqlite.Connection,
    device_id: int,
    event_type_id: int,
) -> int | None:
    """Return the highest event_id for a device+event_type combination.

    This serves as a proxy for the most-recent occurrence.

    Args:
        conn: Active database connection.
        device_id: Device primary key.
        event_type_id: Event type primary key.

    Returns:
        Integer event_id or None.
    """
    row = await fetch_one(
        conn,
        """
        SELECT MAX(event_id) AS max_id FROM event_logs
        WHERE device_id = ? AND event_type_id = ?
        """,
        (device_id, event_type_id),
    )
    return row["max_id"] if row else None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def get_historical_info(
    conn: aiosqlite.Connection,
    device: dict,
    event_type_id: int,
    max_tickets: int = 10,
) -> dict:
    """Run all lookup strategies and return consolidated historical info.

    Strategies run in order; results are merged and deduplicated.

    Args:
        conn: Active database connection.
        device: Device row dict (from the devices table).
        event_type_id: Event type primary key for incident counting.
        max_tickets: Maximum number of tickets to return.

    Returns:
        Dict with ``total_incidents_6m``, ``last_event_id``, ``related_tickets``.
    """
    device_id = device["device_id"]
    site_code = device.get("site_code")
    ip_address = device.get("ip_address")
    device_name = device.get("device_name", "")

    # Run all strategies concurrently-ish (sequential is fine for SQLite)
    results: list[list[dict]] = []

    # Strategy 1: direct map (highest trust)
    direct = await _strategy_direct_map(conn, device_id)
    results.append(direct)

    # Strategy 2: site code
    if site_code:
        site_results = await _strategy_site_code(conn, site_code)
        results.append(site_results)

    # Strategy 3: IP match
    if ip_address:
        ip_results = await _strategy_ip_match(conn, ip_address)
        results.append(ip_results)

    # Strategy 4: fuzzy device name
    if device_name:
        name_results = await _strategy_device_name_fuzzy(conn, device_name)
        results.append(name_results)

    merged = _merge_and_deduplicate(results)[:max_tickets]

    # Approximate "6-month" incident count via the last 20% of event_id range
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
    last_event_id = await get_last_event_id_for_device(conn, device_id, event_type_id)

    return {
        "total_incidents_6m": total_incidents,
        "last_event_id": last_event_id,
        "related_tickets": merged,
    }
