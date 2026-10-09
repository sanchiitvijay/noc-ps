from __future__ import annotations

import aiosqlite
from database.connection import fetch_all, fetch_one

async def build_metrics(conn: aiosqlite.Connection, time_window: str = "all") -> dict:
    """Build proper time-based metrics based on the requested window.
    
    Time window uses the latest event_time in the database as "now" since this 
    is historical data.
    """
    # 1. Determine "now" (max event_time), ignoring malformed rows that lack a date (e.g. just time "20:00:04")
    max_time_row = await fetch_one(conn, "SELECT MAX(event_time) as max_time FROM event_logs WHERE event_time LIKE '202%'")
    max_time = max_time_row["max_time"] if max_time_row else None
    
    if not max_time:
        return {}
        
    # 2. Determine cutoff time and trend format based on window
    cutoff = None
    trend_format = '%Y-%m-%d %H:00:00'
    
    if time_window == "24h":
        cutoff_row = await fetch_one(conn, "SELECT datetime(?, '-24 hours') as ct", (max_time,))
        cutoff = cutoff_row["ct"]
        trend_format = '%Y-%m-%d %H:00:00'
    elif time_window == "7d":
        cutoff_row = await fetch_one(conn, "SELECT datetime(?, '-7 days') as ct", (max_time,))
        cutoff = cutoff_row["ct"]
        trend_format = '%Y-%m-%d'
    elif time_window == "30d":
        cutoff_row = await fetch_one(conn, "SELECT datetime(?, '-30 days') as ct", (max_time,))
        cutoff = cutoff_row["ct"]
        trend_format = '%Y-%m-%d'
    else:  # all
        cutoff = None
        trend_format = '%Y-%W' # Week based for all time to avoid huge lists
        
    where_clause = "WHERE event_logs.event_time >= ?" if cutoff else ""
    params = (cutoff,) if cutoff else ()
    
    # 3. Load lookup table into memory (very small, ~100 rows) for faster mapping
    et_rows = await fetch_all(conn, "SELECT event_type_id, severity, category FROM event_type_lookup")
    et_map = {r["event_type_id"]: r for r in et_rows}
    
    # 4. SINGLE optimized query for total, severity, category, and status
    q_agg = f"""
        SELECT event_type_id, COALESCE(current_status, -1) as status, COUNT(*) as cnt 
        FROM event_logs 
        {where_clause} 
        GROUP BY event_type_id, current_status
    """
    agg_rows = await fetch_all(conn, q_agg, params)
    
    total_events = 0
    severity_dist = {}
    category_dist = {}
    status_dist = {}
    status_map = {1: "Up", 2: "Down", -1: "Unknown"} 
    
    for r in agg_rows:
        cnt = r["cnt"]
        et_id = r["event_type_id"]
        status = r["status"]
        
        total_events += cnt
        
        et = et_map.get(et_id, {"severity": "Unknown", "category": "other"})
        sev = et["severity"] or "Unknown"
        cat = et["category"] or "other"
        
        severity_dist[sev] = severity_dist.get(sev, 0) + cnt
        category_dist[cat] = category_dist.get(cat, 0) + cnt
        
        s_name = status_map.get(status, f"Status {status}")
        status_dist[s_name] = status_dist.get(s_name, 0) + cnt

    severity_order = ["P1", "P2", "P3", "P4", "Critical", "Warning", "Info", "Unknown"]
    sorted_severity_dist = {k: severity_dist[k] for k in severity_order if k in severity_dist}
    for k in sorted(severity_dist.keys()):
        if k not in sorted_severity_dist:
            sorted_severity_dist[k] = severity_dist[k]
    severity_dist = sorted_severity_dist

    # 5. Top 20 devices optimized (No JOINs on the large table)
    q_top = f"""
        SELECT device_id, COUNT(*) as cnt 
        FROM event_logs 
        {where_clause} 
        GROUP BY device_id 
        ORDER BY cnt DESC 
        LIMIT 20
    """
    top_devices_raw = await fetch_all(conn, q_top, params)
    
    dev_ids = [r["device_id"] for r in top_devices_raw if r["device_id"] is not None]
    top_devices = []
    
    if dev_ids:
        placeholders = ",".join(["?"] * len(dev_ids))
        q_devs = f"SELECT device_id, device_name FROM devices WHERE device_id IN ({placeholders})"
        dev_rows = await fetch_all(conn, q_devs, tuple(dev_ids))
        dev_map = {r["device_id"]: r["device_name"] for r in dev_rows}
        
        for r in top_devices_raw:
            dname = dev_map.get(r["device_id"], "Unknown Device")
            top_devices.append({"device_name": dname, "event_count": r["cnt"]})

    # 6. Time-based trend
    q_trend = f"""
        SELECT strftime('{trend_format}', event_time) as time_bucket, COUNT(*) as cnt
        FROM event_logs
        {where_clause}
        GROUP BY time_bucket
        ORDER BY time_bucket ASC
    """
    trend_rows = await fetch_all(conn, q_trend, params)
    events_trend = [{"time": r["time_bucket"], "count": r["cnt"]} for r in trend_rows]

    where_e = where_clause.replace("event_logs.", "e.")
    
    # 7. Busiest sites
    q_sites = f"""
        SELECT s.label as site_name, s.code as site_code, COUNT(e.event_id) as count
        FROM event_logs e
        JOIN devices d ON e.device_id = d.device_id
        LEFT JOIN sites s ON d.site_code = s.code
        {where_e}
        GROUP BY s.code, s.label
        ORDER BY count DESC
        LIMIT 10
    """
    busiest_sites = [dict(r) for r in await fetch_all(conn, q_sites, params)]

    # 8. Alerts by state
    q_states = f"""
        SELECT s.state, COUNT(e.event_id) as count
        FROM event_logs e
        JOIN devices d ON e.device_id = d.device_id
        JOIN sites s ON d.site_code = s.code
        {where_e}
        GROUP BY s.state
        ORDER BY count DESC
    """
    alerts_by_state = [dict(r) for r in await fetch_all(conn, q_states, params)]

    # 9. Top event types
    q_top_types = f"""
        SELECT l.event_type_name as name, l.severity, COUNT(e.event_id) as count
        FROM event_logs e
        JOIN event_type_lookup l ON e.event_type_id = l.event_type_id
        {where_e}
        GROUP BY l.event_type_id, l.event_type_name, l.severity
        ORDER BY count DESC
        LIMIT 10
    """
    top_event_types = [dict(r) for r in await fetch_all(conn, q_top_types, params)]

    return {
        "time_window": time_window,
        "total_events": total_events,
        "alert_volume": total_events,
        "events_by_severity": severity_dist,
        "events_by_category": category_dist,
        "top_alerting_devices": top_devices,
        "events_by_status": status_dist,
        "events_trend": events_trend,
        "busiest_sites": busiest_sites,
        "alerts_by_state": alerts_by_state,
        "top_event_types": top_event_types
    }
