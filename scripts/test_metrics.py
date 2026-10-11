import sqlite3

def run():
    conn = sqlite3.connect('noc_automation_4.db')
    conn.row_factory = sqlite3.Row
    
    max_time_row = conn.execute("SELECT MAX(event_time) as mt FROM event_logs").fetchone()
    max_time = max_time_row['mt']
    print(f"Max time: {max_time}")
    
    cutoff = conn.execute("SELECT datetime(?, '-24 hours') as ct", (max_time,)).fetchone()['ct']
    print(f"Cutoff 24h: {cutoff}")
    
    res = conn.execute("SELECT COUNT(*) as c FROM event_logs WHERE event_time >= ?", (cutoff,)).fetchone()
    print(f"24h events: {res['c']}")
    
    res = conn.execute("""
    SELECT strftime('%Y-%m-%d %H:00:00', event_time) as time_bucket, COUNT(*) as cnt
    FROM event_logs
    WHERE event_time >= ?
    GROUP BY time_bucket
    """, (cutoff,)).fetchall()
    
    for r in res:
        print(dict(r))

run()
