"""
NOC Automation - Standard Query Function (Backend Integration)
==============================================================

Single function that accepts any combination of inputs and returns
standardized ticket + event + device output.

Usage:
    # Import and call from Backend code
    from query_noc_db import query_noc_db
    results = query_noc_db(ip_address="10.159.83.95", event_name="Node Down")

    # Or run directly to test
    python query_noc_db.py --ip 10.159.83.95
    python query_noc_db.py --event "Node Down"
    python query_noc_db.py --device "%Erlanger%"
    python query_noc_db.py --ip 10.159.83.95 --event "Node Down"
"""

import sqlite3
import json
import os
import argparse
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "noc-automation2.db")

# --------------------------------------------------------------------------
# STANDARD QUERY — matches master_query_templates.sql
# --------------------------------------------------------------------------
STANDARD_QUERY = """
SELECT
    t.ticket_number,
    t.ticket_type,
    t.state,
    t.created_on,
    t.updated_on,
    t.short_description,
    t.description,
    t.work_notes,
    CASE
        WHEN e.event_type_name IN ('Node Down', 'EventType-5000', 'EventType-5001')  THEN 'P1'
        WHEN e.event_type_name IN ('Interface Down', 'Interface Status Changed')      THEN 'P2'
        WHEN e.event_type_name IN ('Node Up', 'Interface Up')                         THEN 'P3'
        ELSE 'P4'
    END AS severity,
    COUNT(e.event_id) AS frequency,
    d.machine_type AS device_type,
    d.device_name,
    d.ip_address,
    e.event_time,
    d.device_id,
    e.message
FROM devices d
JOIN event_logs e        ON e.device_id = d.device_id
LEFT JOIN device_ticket_map m ON m.device_id = d.device_id
LEFT JOIN sn_tickets t        ON t.ticket_id = m.ticket_id
WHERE 1=1
  AND (:ip_address    IS NULL OR d.ip_address      = :ip_address)
  AND (:device_name   IS NULL OR d.device_name     LIKE :device_name)
  AND (:device_type   IS NULL OR d.machine_type    LIKE :device_type)
  AND (:event_name    IS NULL OR e.event_type_name = :event_name)
  AND (:device_id     IS NULL OR d.device_id       = :device_id)
  AND (:error_message IS NULL OR e.message         LIKE :error_message)
GROUP BY d.device_id, COALESCE(t.ticket_id, 0)
ORDER BY t.created_on DESC
LIMIT 50;
"""


def query_noc_db(
    ip_address:    Optional[str] = None,
    device_name:   Optional[str] = None,
    device_type:   Optional[str] = None,
    event_name:    Optional[str] = None,
    device_id:     Optional[int] = None,
    error_message: Optional[str] = None,
    db_path:       str = DB_PATH,
) -> List[Dict[str, Any]]:
    """
    Standard query function for the NOC Automation database.

    INPUTS (pass only what you have, leave rest as None):
        ip_address    — exact match, e.g. "10.159.83.95"
        device_name   — LIKE match, e.g. "%Erlanger%" or exact "8395-Erlanger-KY"
        device_type   — LIKE match, e.g. "%Cisco%"
        event_name    — exact match, e.g. "Node Down", "Interface Down"
        device_id     — exact match, e.g. 5457
        error_message — LIKE match, e.g. "%unreachable%"

    OUTPUT (list of dicts, each dict has these 16 keys):
        ticket_number, ticket_type, state, created_on, updated_on,
        short_description, description, work_notes,
        severity, frequency,
        device_type, device_name, ip_address, event_time, device_id, message
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    params = {
        "ip_address":    ip_address,
        "device_name":   device_name,
        "device_type":   device_type,
        "event_name":    event_name,
        "device_id":     device_id,
        "error_message": error_message,
    }

    cur.execute(STANDARD_QUERY, params)
    results = [dict(row) for row in cur.fetchall()]
    conn.close()
    return results


# --------------------------------------------------------------------------
# CLI: Run directly to test
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="NOC DB Standard Query — test any input combination",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python query_noc_db.py --ip 10.159.83.95
  python query_noc_db.py --event "Node Down"
  python query_noc_db.py --device "%Erlanger%"
  python query_noc_db.py --device-id 5457
  python query_noc_db.py --device-type "%Cisco%"
  python query_noc_db.py --message "%unreachable%"
  python query_noc_db.py --ip 10.159.83.95 --event "Node Down"
        """,
    )
    parser.add_argument("--ip",          type=str, default=None, help="IP address (exact)")
    parser.add_argument("--device",      type=str, default=None, help="Device name (LIKE match, use %% for wildcard)")
    parser.add_argument("--device-type", type=str, default=None, help="Device/machine type (LIKE match)")
    parser.add_argument("--event",       type=str, default=None, help="Event name (exact, e.g. 'Node Down')")
    parser.add_argument("--device-id",   type=int, default=None, help="Device ID (exact)")
    parser.add_argument("--message",     type=str, default=None, help="Error message text (LIKE match)")
    parser.add_argument("--json",        action="store_true",     help="Output raw JSON instead of formatted table")

    args = parser.parse_args()

    # If no input provided, show a quick demo
    if not any([args.ip, args.device, args.device_type, args.event, args.device_id, args.message]):
        print("No input provided. Running demo: --ip 10.159.83.95 --event 'Node Down'\n")
        args.ip = "10.159.83.95"
        args.event = "Node Down"

    results = query_noc_db(
        ip_address=args.ip,
        device_name=args.device,
        device_type=args.device_type,
        event_name=args.event,
        device_id=args.device_id,
        error_message=args.message,
    )

    # Print inputs used
    print("=" * 70)
    print("  NOC DB STANDARD QUERY")
    print("=" * 70)
    print("\n  INPUTS:")
    if args.ip:          print(f"    ip_address    = {args.ip}")
    if args.device:      print(f"    device_name   = {args.device}")
    if args.device_type: print(f"    device_type   = {args.device_type}")
    if args.event:       print(f"    event_name    = {args.event}")
    if args.device_id:   print(f"    device_id     = {args.device_id}")
    if args.message:     print(f"    error_message = {args.message}")
    print(f"\n  RESULTS: {len(results)} rows returned\n")

    if not results:
        print("  No matching records found.")
        return

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return

    # Formatted output
    for i, row in enumerate(results, 1):
        print(f"  --- Result #{i} ---")
        print(f"  ticket_number   : {row['ticket_number']}")
        print(f"  ticket_type     : {row['ticket_type']}")
        print(f"  state           : {row['state']}")
        print(f"  created_on      : {row['created_on']}")
        print(f"  updated_on      : {row['updated_on']}")
        print(f"  short_description: {row['short_description']}")

        desc = row.get('description') or '(empty)'
        if len(desc) > 120:
            desc = desc[:120] + '...'
        print(f"  description     : {desc}")

        wn = row.get('work_notes') or '(empty)'
        if len(wn) > 120:
            wn = wn[:120] + '...'
        print(f"  work_notes      : {wn}")

        print(f"  severity        : {row['severity']}")
        print(f"  frequency       : {row['frequency']}")
        print(f"  device_type     : {row['device_type']}")
        print(f"  device_name     : {row['device_name']}")
        print(f"  ip_address      : {row['ip_address']}")
        print(f"  event_time      : {row['event_time']}")
        print(f"  device_id       : {row['device_id']}")
        print(f"  message         : {row['message']}")
        print()

    print("=" * 70)


if __name__ == "__main__":
    main()
