import sqlite3
import time

def run():
    conn = sqlite3.connect('noc_automation_4.db')
    conn.row_factory = sqlite3.Row
    
    t0 = time.time()
    
    # Let's say user filters by severity = 'P4' and page = 2
    severity = 'P4'
    search = 'failed'
    device_id = None
    
    conditions = []
    params = []
    
    if severity:
        et_rows = conn.execute("SELECT event_type_id FROM event_type_lookup WHERE severity = ?", (severity,)).fetchall()
        et_ids = [str(r["event_type_id"]) for r in et_rows]
        if et_ids:
            placeholders = ",".join(et_ids)
            conditions.append(f"event_type_id IN ({placeholders})")
        else:
            conditions.append("1=0") # No matching severity
            
    if search:
        conditions.append("(message LIKE ? OR raw_detail LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
        
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    # COUNT
    t1 = time.time()
    count_query = f"SELECT COUNT(*) as cnt FROM event_logs {where_clause}"
    cnt = conn.execute(count_query, params).fetchone()["cnt"]
    t2 = time.time()
    print(f"COUNT took {t2-t1:.4f}s. Total: {cnt}")
    
    # DATA
    page_size = 50
    offset = 50
    
    # First get the specific event_ids matching the filter
    data_query = f"""
        SELECT *
        FROM event_logs
        {where_clause}
        ORDER BY event_id DESC
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])
    t3 = time.time()
    rows = conn.execute(data_query, params).fetchall()
    
    # Now join manually in python (since it's only 50 rows!)
    dev_ids = list(set([r["device_id"] for r in rows if r["device_id"] is not None]))
    dev_map = {}
    if dev_ids:
        placeholders = ",".join(["?"] * len(dev_ids))
        d_rows = conn.execute(f"SELECT device_id, device_name, ip_address, site_code FROM devices WHERE device_id IN ({placeholders})", dev_ids).fetchall()
        dev_map = {r["device_id"]: r for r in d_rows}
        
    et_ids = list(set([r["event_type_id"] for r in rows if r["event_type_id"] is not None]))
    et_map = {}
    if et_ids:
        placeholders = ",".join(["?"] * len(et_ids))
        et_rows = conn.execute(f"SELECT event_type_id, severity, category FROM event_type_lookup WHERE event_type_id IN ({placeholders})", et_ids).fetchall()
        et_map = {r["event_type_id"]: r for r in et_rows}
        
    final_data = []
    for r in rows:
        d = dict(r)
        d_info = dev_map.get(r["device_id"])
        if d_info:
            d["device_name"] = d_info["device_name"]
            d["ip_address"] = d_info["ip_address"]
            d["site_code"] = d_info["site_code"]
            
        e_info = et_map.get(r["event_type_id"])
        if e_info:
            d["severity"] = e_info["severity"]
            d["category"] = e_info["category"]
            
        final_data.append(d)
        
    t4 = time.time()
    print(f"DATA took {t4-t3:.4f}s.")
    print(f"Total time {t4-t0:.4f}s.")

run()
