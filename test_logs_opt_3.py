import sqlite3
import time

def run():
    conn = sqlite3.connect('noc_automation_4.db')
    conn.row_factory = sqlite3.Row
    t0 = time.time()
    query = """
        SELECT COUNT(*) AS cnt 
        FROM event_logs el
        LEFT JOIN devices d ON el.device_id = d.device_id
        LEFT JOIN event_type_lookup etl ON el.event_type_id = etl.event_type_id
    """
    cnt = conn.execute(query).fetchone()["cnt"]
    t1 = time.time()
    print(f"COUNT took {t1-t0:.4f}s. Total: {cnt}")
    
    query2 = """
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
        FROM event_logs el
        LEFT JOIN devices d          ON el.device_id     = d.device_id
        LEFT JOIN event_type_lookup etl ON el.event_type_id = etl.event_type_id
        ORDER BY el.event_id DESC
        LIMIT 50 OFFSET 50
    """
    t2 = time.time()
    rows = conn.execute(query2).fetchall()
    t3 = time.time()
    print(f"DATA took {t3-t2:.4f}s.")

run()
