import sqlite3
import time

def run():
    conn = sqlite3.connect('noc_automation_4.db')
    conn.row_factory = sqlite3.Row
    
    t0 = time.time()
    max_time_row = conn.execute("SELECT MAX(event_time) as mt FROM event_logs").fetchone()
    max_time = max_time_row['mt']
    
    cutoff = conn.execute("SELECT datetime(?, '-30 days') as ct", (max_time,)).fetchone()['ct']
    where_clause = "WHERE event_time >= ?"
    params = (cutoff,)
    
    # 1. Fetch event type lookup (tiny)
    et_rows = conn.execute("SELECT event_type_id, severity, category FROM event_type_lookup").fetchall()
    et_map = {r["event_type_id"]: r for r in et_rows}
    
    # 2. Single scan for total, severity, category, status
    q1 = f"SELECT event_type_id, COALESCE(current_status, -1) as status, COUNT(*) as cnt FROM event_logs {where_clause} GROUP BY event_type_id, current_status"
    agg_rows = conn.execute(q1, params).fetchall()
    
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

    # 3. Top 20 devices without join
    q2 = f"SELECT device_id, COUNT(*) as cnt FROM event_logs {where_clause} GROUP BY device_id ORDER BY cnt DESC LIMIT 20"
    top_devices_raw = conn.execute(q2, params).fetchall()
    
    dev_ids = [r["device_id"] for r in top_devices_raw if r["device_id"] is not None]
    top_devices = []
    if dev_ids:
        placeholders = ",".join(["?"] * len(dev_ids))
        dev_rows = conn.execute(f"SELECT device_id, device_name FROM devices WHERE device_id IN ({placeholders})", dev_ids).fetchall()
        dev_map = {r["device_id"]: r["device_name"] for r in dev_rows}
        for r in top_devices_raw:
            dname = dev_map.get(r["device_id"], "Unknown Device")
            top_devices.append({"device_name": dname, "event_count": r["cnt"]})
            
    # 4. Trend
    q_trend = f"SELECT strftime('%Y-%m-%d', event_time) as time_bucket, COUNT(*) as cnt FROM event_logs {where_clause} GROUP BY time_bucket ORDER BY time_bucket ASC"
    trend_rows = conn.execute(q_trend, params).fetchall()
    
    t1 = time.time()
    print(f"Time taken: {t1 - t0:.3f} seconds")
    print(f"Total: {total_events}")
    print(f"Top 2 devices: {top_devices[:2]}")

run()
