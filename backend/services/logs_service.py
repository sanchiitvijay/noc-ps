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
    page_size: int = 50,
) -> dict:
    conditions: list[str] = []
    params: list = []

    if device_id is not None:
        conditions.append("event_logs.device_id = ?")
        params.append(device_id)

    if event_type_id is not None:
        conditions.append("event_logs.event_type_id = ?")
        params.append(event_type_id)

    if severity is not None:
        # Pre-resolve severity to event_type_ids to avoid joining the whole table
        et_rows = await fetch_all(
            conn, 
            "SELECT event_type_id FROM event_type_lookup WHERE severity = ?", 
            (severity,)
        )
        valid_et_ids = [str(r["event_type_id"]) for r in et_rows]
        if valid_et_ids:
            placeholders = ",".join(valid_et_ids)
            conditions.append(f"event_logs.event_type_id IN ({placeholders})")
        else:
            # Severity matched nothing, so return no results immediately
            return {"data": [], "meta": paginate(0, page, page_size)}

    if search:
        conditions.append("(event_logs.message LIKE ? OR event_logs.raw_detail LIKE ?)")
        like_term = f"%{search}%"
        params.extend([like_term, like_term])

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Extremely fast COUNT (no joins)
    count_query = f"SELECT COUNT(*) AS cnt FROM event_logs {where_clause}"
    count_row = await fetch_one(conn, count_query, tuple(params))
    total = count_row["cnt"] if count_row else 0

    if total == 0:
        return {"data": [], "meta": paginate(0, page, page_size)}

    offset = get_offset(page, page_size)

    # 1. Fetch ONLY the base event_logs (fast, uses index for ORDER BY)
    base_data_query = f"""
        SELECT *
        FROM event_logs
        {where_clause}
        ORDER BY event_id DESC
        LIMIT ? OFFSET ?
    """
    base_rows = await fetch_all(conn, base_data_query, tuple(params) + (page_size, offset))

    # 2. Extract IDs for related entities
    dev_ids = list({r["device_id"] for r in base_rows if r["device_id"] is not None})
    et_ids = list({r["event_type_id"] for r in base_rows if r["event_type_id"] is not None})

    # 3. Fetch related devices (batch lookup)
    dev_map = {}
    if dev_ids:
        placeholders = ",".join(["?"] * len(dev_ids))
        d_rows = await fetch_all(
            conn,
            f"SELECT device_id, device_name, ip_address, site_code FROM devices WHERE device_id IN ({placeholders})",
            tuple(dev_ids),
        )
        dev_map = {r["device_id"]: dict(r) for r in d_rows}

    # 4. Fetch related event types (batch lookup)
    et_map = {}
    if et_ids:
        placeholders = ",".join(["?"] * len(et_ids))
        et_rows = await fetch_all(
            conn,
            f"SELECT event_type_id, severity, category FROM event_type_lookup WHERE event_type_id IN ({placeholders})",
            tuple(et_ids),
        )
        et_map = {r["event_type_id"]: dict(r) for r in et_rows}

    # 5. Enrich rows purely in Python (instant)
    enriched_rows = []
    for r in base_rows:
        row_dict = dict(r)
        
        # Enrich device
        d_info = dev_map.get(row_dict.get("device_id"))
        row_dict["device_name"] = d_info["device_name"] if d_info else None
        row_dict["ip_address"] = d_info["ip_address"] if d_info else None
        row_dict["site_code"] = d_info["site_code"] if d_info else None
        
        # Enrich event type
        e_info = et_map.get(row_dict.get("event_type_id"))
        row_dict["severity"] = e_info["severity"] if e_info else None
        row_dict["category"] = e_info["category"] if e_info else None
        
        enriched_rows.append(row_dict)

    return {
        "data": enriched_rows,
        "meta": paginate(total, page, page_size),
    }


# ---------------------------------------------------------------------------
# Activity logs
# ---------------------------------------------------------------------------


async def get_activity_logs(
    conn: aiosqlite.Connection,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    count_row = await fetch_one(conn, "SELECT COUNT(*) AS cnt FROM activity_logs")
    total = count_row["cnt"] if count_row else 0

    if total == 0:
        return {"data": [], "meta": paginate(0, page, page_size)}

    offset = get_offset(page, page_size)

    # Similar optimization for activity logs, avoid joining full users table in ORDER BY.
    # First fetch the activity logs directly.
    base_rows = await fetch_all(
        conn,
        """
        SELECT *
        FROM activity_logs
        ORDER BY id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    )

    # Extract user IDs
    user_ids = list({r["user_id"] for r in base_rows if r["user_id"] is not None})
    
    # Batch fetch usernames
    user_map = {}
    if user_ids:
        placeholders = ",".join(["?"] * len(user_ids))
        u_rows = await fetch_all(
            conn,
            f"SELECT id, username FROM users WHERE id IN ({placeholders})",
            tuple(user_ids),
        )
        user_map = {r["id"]: r["username"] for r in u_rows}

    # Enrich
    enriched_rows = []
    for r in base_rows:
        row_dict = dict(r)
        row_dict["username"] = user_map.get(row_dict.get("user_id"))
        enriched_rows.append(row_dict)

    return {
        "data": enriched_rows,
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
    return await execute_write(
        conn,
        """
        INSERT INTO activity_logs
            (user_id, action, endpoint, ip_address, request_body, response_status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, action, endpoint, ip_address, request_body, response_status),
    )
