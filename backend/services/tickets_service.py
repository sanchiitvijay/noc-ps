"""
Tickets service — logic for retrieving ticket data.
"""

from __future__ import annotations

import json
import aiosqlite
from database.connection import fetch_all, fetch_one
from utils.pagination import get_offset, paginate

async def get_tickets(
    conn: aiosqlite.Connection,
    q: str = "",
    kind: str = "",
    status: str = "",
    linked: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    where_clauses = ["1=1"]
    params = []

    if q:
        where_clauses.append("(t.ticket_number LIKE ? OR t.short_description LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    
    if kind:
        where_clauses.append("t.ticket_type = ?")
        params.append(kind)

    if status:
        where_clauses.append("t.state = ?")
        params.append(status)

    if linked in ("yes", "no"):
        if linked == "yes":
            where_clauses.append("EXISTS (SELECT 1 FROM device_ticket_map m WHERE m.ticket_id=t.ticket_id)")
        else:
            where_clauses.append("NOT EXISTS (SELECT 1 FROM device_ticket_map m WHERE m.ticket_id=t.ticket_id)")

    w = " AND ".join(where_clauses)
    
    # Total count
    count_row = await fetch_one(conn, f"SELECT COUNT(*) AS cnt FROM sn_tickets t WHERE {w}", tuple(params))
    total = count_row["cnt"] if count_row else 0

    if total == 0:
        return {"data": [], "meta": paginate(0, page, page_size), "kinds": [], "statuses": []}

    offset = get_offset(page, page_size)

    # Main list query
    query = f"""
        SELECT t.ticket_id, t.ticket_number, t.ticket_type, t.state, t.assignment_group,
               t.created_on, t.closed_at, t.short_description,
               (SELECT COUNT(*) FROM device_ticket_map m WHERE m.ticket_id=t.ticket_id) links,
               (SELECT MAX(confidence) FROM device_ticket_map m WHERE m.ticket_id=t.ticket_id) best_link
        FROM sn_tickets t 
        WHERE {w} 
        ORDER BY t.created_on DESC 
        LIMIT ? OFFSET ?
    """
    items = await fetch_all(conn, query, tuple(params) + (page_size, offset))

    # Kinds aggregation
    q_kinds = "SELECT ticket_type as kind, COUNT(*) n FROM sn_tickets GROUP BY ticket_type ORDER BY n DESC"
    kinds = await fetch_all(conn, q_kinds)

    # Statuses aggregation
    q_statuses = "SELECT state, COUNT(*) n FROM sn_tickets GROUP BY state ORDER BY n DESC"
    statuses = await fetch_all(conn, q_statuses)

    return {
        "data": [dict(r) for r in items],
        "meta": paginate(total, page, page_size),
        "kinds": [dict(r) for r in kinds],
        "statuses": [dict(r) for r in statuses]
    }


async def get_ticket_details(
    conn: aiosqlite.Connection,
    number: str,
) -> dict | None:
    # Basic info
    t = await fetch_one(conn, "SELECT * FROM sn_tickets WHERE ticket_number=?", (number,))
    if not t:
        return None
        
    t_dict = dict(t)
    # Handle JSON arrays if they are strings
    for k in ["extracted_site_codes", "extracted_ips", "extracted_device_names"]:
        if t_dict.get(k):
            try:
                t_dict[k] = json.loads(t_dict[k])
            except:
                pass

    # Links
    links = await fetch_all(
        conn, 
        """SELECT m.match_type as kind, m.match_value as value, m.confidence, 
                  d.site_code, d.device_id, d.device_name, d.machine_type as role, 
                  s.label as site_label
           FROM device_ticket_map m 
           LEFT JOIN devices d ON d.device_id = m.device_id
           LEFT JOIN sites s ON s.code = d.site_code 
           WHERE m.ticket_id=? 
           ORDER BY m.confidence DESC""", 
        (t_dict["ticket_id"],)
    )

    return {
        "ticket": t_dict,
        "links": [dict(r) for r in links]
    }
