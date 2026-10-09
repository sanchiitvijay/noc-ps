"""
Sites service — logic for retrieving site data and stats.
"""

from __future__ import annotations

import aiosqlite
from database.connection import fetch_all, fetch_one
from utils.pagination import get_offset, paginate

async def get_sites(
    conn: aiosqlite.Connection,
    q: str = "",
    state: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    where_clauses = ["1=1"]
    params = []

    if q:
        where_clauses.append("(s.code = ? OR s.label LIKE ? OR s.city LIKE ?)")
        params.extend([q, f"%{q}%", f"%{q}%"])
    
    if state:
        where_clauses.append("s.state = ?")
        params.append(state)

    w = " AND ".join(where_clauses)
    
    # Total count
    count_row = await fetch_one(conn, f"SELECT COUNT(*) AS cnt FROM sites s WHERE {w}", tuple(params))
    total = count_row["cnt"] if count_row else 0

    if total == 0:
        return {"data": [], "meta": paginate(0, page, page_size), "states": []}

    offset = get_offset(page, page_size)

    # Main list query
    query = f"""
        WITH ev AS (
            SELECT d.site_code, COUNT(*) alerts, 
                   SUM(CASE WHEN l.severity='P1' THEN 1 ELSE 0 END) p1, 
                   MAX(e.event_time) last_event 
            FROM event_logs e 
            JOIN devices d ON e.device_id = d.device_id 
            LEFT JOIN event_type_lookup l ON e.event_type_id = l.event_type_id 
            WHERE d.site_code IS NOT NULL 
            GROUP BY d.site_code
        ),
        dv AS (
            SELECT site_code, COUNT(*) devices 
            FROM devices 
            WHERE site_code IS NOT NULL 
            GROUP BY site_code
        ),
        tk AS (
            SELECT d.site_code, COUNT(DISTINCT m.ticket_id) tickets 
            FROM device_ticket_map m 
            JOIN devices d ON m.device_id = d.device_id 
            WHERE d.site_code IS NOT NULL 
            GROUP BY d.site_code
        )
        SELECT s.code, s.label, s.city, s.state, s.address, 
               COALESCE(dv.devices, 0) devices, 
               COALESCE(ev.alerts, 0) alerts,
               COALESCE(ev.p1, 0) p1, 
               COALESCE(tk.tickets, 0) tickets, 
               ev.last_event
        FROM sites s 
        LEFT JOIN ev ON ev.site_code=s.code 
        LEFT JOIN dv ON dv.site_code=s.code 
        LEFT JOIN tk ON tk.site_code=s.code
        WHERE {w} 
        ORDER BY alerts DESC, s.code 
        LIMIT ? OFFSET ?
    """
    items = await fetch_all(conn, query, tuple(params) + (page_size, offset))

    # States aggregation
    q_states = """
        WITH ev AS (
            SELECT d.site_code, COUNT(*) alerts, 
                   SUM(CASE WHEN l.severity='P1' THEN 1 ELSE 0 END) p1
            FROM event_logs e 
            JOIN devices d ON e.device_id = d.device_id
            LEFT JOIN event_type_lookup l ON e.event_type_id = l.event_type_id 
            WHERE d.site_code IS NOT NULL
            GROUP BY d.site_code
        )
        SELECT s.state, COUNT(*) sites, 
               COALESCE(SUM(ev.alerts), 0) alerts, 
               COALESCE(SUM(ev.p1), 0) p1
        FROM sites s 
        LEFT JOIN ev ON ev.site_code = s.code 
        WHERE s.state IS NOT NULL 
        GROUP BY s.state
    """
    states = await fetch_all(conn, q_states)

    return {
        "data": [dict(r) for r in items],
        "meta": paginate(total, page, page_size),
        "states": [dict(r) for r in states]
    }


async def get_site_details(
    conn: aiosqlite.Connection,
    code: str,
) -> dict | None:
    # Basic info
    s = await fetch_one(conn, "SELECT * FROM sites WHERE code=?", (code,))
    if not s:
        return None

    # Devices in site
    devices = await fetch_all(
        conn, 
        """SELECT d.device_id, d.device_name, d.machine_type, d.ip_address,
                  COUNT(e.event_id) as event_count
           FROM devices d 
           LEFT JOIN event_logs e ON d.device_id = e.device_id
           WHERE d.site_code=? 
           GROUP BY d.device_id
           ORDER BY event_count DESC""", 
        (code,)
    )

    # Alerts by category
    by_cat = await fetch_all(
        conn, 
        """SELECT l.category, COUNT(*) n 
           FROM event_logs e 
           JOIN devices d ON e.device_id = d.device_id
           JOIN event_type_lookup l ON e.event_type_id = l.event_type_id
           WHERE d.site_code=? 
           GROUP BY l.category 
           ORDER BY n DESC""", 
        (code,)
    )

    # Alerts by day
    by_day = await fetch_all(
        conn, 
        """SELECT substr(e.event_time, 1, 10) day, COUNT(*) n, 
                  SUM(CASE WHEN l.severity='P1' THEN 1 ELSE 0 END) p1 
           FROM event_logs e
           JOIN devices d ON e.device_id = d.device_id
           JOIN event_type_lookup l ON e.event_type_id = l.event_type_id
           WHERE d.site_code=? AND e.event_time IS NOT NULL 
           GROUP BY day 
           ORDER BY day""", 
        (code,)
    )

    # Related Tickets
    tickets = await fetch_all(
        conn, 
        """SELECT t.ticket_number as number, t.ticket_type as kind, t.state, 
                  t.created_on as created_at, t.short_description,
                  MAX(m.confidence) as confidence
           FROM device_ticket_map m 
           JOIN sn_tickets t ON t.ticket_id = m.ticket_id 
           JOIN devices d ON m.device_id = d.device_id
           WHERE d.site_code=?
           GROUP BY t.ticket_id 
           ORDER BY t.created_on DESC 
           LIMIT 25""", 
        (code,)
    )

    # Recent alerts
    recent = await fetch_all(
        conn, 
        """SELECT e.event_id as id, e.event_time as ts, l.event_type_name as name, 
                  l.severity, l.category, d.device_name, e.current_status as status, e.message 
           FROM event_logs e
           JOIN devices d ON e.device_id = d.device_id
           JOIN event_type_lookup l ON e.event_type_id = l.event_type_id
           WHERE d.site_code=? 
           ORDER BY e.event_time DESC 
           LIMIT 30""", 
        (code,)
    )

    return {
        "site": dict(s),
        "devices": [dict(r) for r in devices],
        "by_category": [dict(r) for r in by_cat],
        "by_day": [dict(r) for r in by_day],
        "tickets": [dict(r) for r in tickets],
        "recent": [dict(r) for r in recent]
    }
