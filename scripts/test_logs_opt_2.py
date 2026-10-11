import sqlite3
import time

def run():
    conn = sqlite3.connect('noc_automation_4.db')
    conn.row_factory = sqlite3.Row
    t0 = time.time()
    cnt = conn.execute("SELECT COUNT(*) as cnt FROM event_logs").fetchone()["cnt"]
    t1 = time.time()
    print(f"COUNT took {t1-t0:.4f}s. Total: {cnt}")

run()
