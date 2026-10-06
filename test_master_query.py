"""
Master Query Tester
===================
Tests all 6 input types against noc_automation.db and prints results.

Usage:
    python test_master_query.py
    python test_master_query.py --ip 10.159.83.95
    python test_master_query.py --device "8395-Erlanger-KY"
    python test_master_query.py --event "EventType-56"
    python test_master_query.py --device-id 5457
    python test_master_query.py --device-type "Versa"
    python test_master_query.py --message "EventType-56"
    python test_master_query.py --ip 10.159.83.95 --event "EventType-56"
"""

import sqlite3
import os
import argparse

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "noc_automation2.db")


def run_query(ip=None, device=None, event=None, device_id=None, device_type=None, message=None):
    """Run the master query with any combination of inputs."""

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at '{DB_PATH}'")
        print("Run 'python etl_pipeline.py' first to create the database.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Build WHERE clause dynamically based on which inputs are provided
    conditions = []
    params = []

    if ip:
        conditions.append("d.ip_address = ?")
        params.append(ip)
    if device:
        # Support partial match with % or exact match
        if "%" in device:
            conditions.append("d.device_name LIKE ?")
        else:
            conditions.append("(d.device_name = ? OR d.device_name LIKE ?)")
            params.append(device)
            device = f"%{device}%"
        params.append(device)
    if event:
        conditions.append("e.event_type_name = ?")
        params.append(event)
    if device_id:
        conditions.append("d.device_id = ?")
        params.append(device_id)
    if device_type:
        conditions.append("d.machine_type LIKE ?")
        params.append(f"%{device_type}%")
    if message:
        conditions.append("e.message LIKE ?")
        params.append(f"%{message}%")

    if not conditions:
        print("ERROR: Provide at least one input filter.")
        print("Options: --ip, --device, --event, --device-id, --device-type, --message")
        return

    where_clause = " AND ".join(conditions)

    # Use JOIN instead of LEFT JOIN for event_logs when filtering on event columns
    event_join = "JOIN" if (event or message) else "LEFT JOIN"

    query = f"""
    SELECT 
        -- Ticket output
        t.ticket_number,
        t.ticket_type,
        t.state,
        t.created_on,
        t.updated_on,
        t.short_description,
        t.description,
        t.work_notes,
        -- Severity (derived from event type)
        CASE 
            WHEN e.event_type_name IN ('Node Down', 'EventType-5000', 'EventType-5001')  THEN 'P1'
            WHEN e.event_type_name IN ('Interface Down', 'Interface Status Changed')      THEN 'P2'
            WHEN e.event_type_name IN ('Node Up', 'Interface Up')                         THEN 'P3'
            ELSE 'P4'
        END AS severity,
        -- Frequency: count of matching events for this device
        COUNT(e.event_id) AS frequency,
        -- Device output
        d.machine_type  AS device_type,
        d.device_name,
        d.ip_address,
        e.event_time,
        d.device_id,
        e.message
    FROM sn_tickets t
    JOIN device_ticket_map m ON m.ticket_id = t.ticket_id
    JOIN devices d           ON d.device_id = m.device_id
    {event_join} event_logs e ON e.device_id = d.device_id
    WHERE {where_clause}
    GROUP BY t.ticket_id, d.device_id
    ORDER BY t.created_on DESC
    LIMIT 20;
    """

    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    # Print header
    print("=" * 70)
    print(" MASTER QUERY RESULTS")
    print("=" * 70)
    print(f"\nFilters applied:")
    if ip:          print(f"  IP Address   : {ip}")
    if device:      print(f"  Device Name  : {device}")
    if event:       print(f"  Event Name   : {event}")
    if device_id:   print(f"  Device ID    : {device_id}")
    if device_type: print(f"  Device Type  : {device_type}")
    if message:     print(f"  Message      : {message}")
    print(f"\nResults found: {len(rows)}")

    if not rows:
        print("\nNo matching tickets found for the given input.")
        conn.close()
        return

    # Print each result
    for i, row in enumerate(rows, 1):
        print(f"\n{'-' * 70}")
        print(f"  RESULT #{i}")
        print(f"{'-' * 70}")
        row_dict = dict(row)
        for col in columns:
            val = row_dict[col]
            if val is None:
                val = "(empty)"
            elif isinstance(val, str) and len(val) > 150:
                val = val[:150].replace("\r", "") + "... [TRUNCATED]"
            print(f"  {col:20s}: {val}")

    conn.close()
    print(f"\n{'=' * 70}")
    print(f"  Total: {len(rows)} results returned")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(
        description="Master Query Tester — search by any input, get full ticket + event output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_master_query.py --ip 10.159.83.95
  python test_master_query.py --device "8395-Erlanger-KY"
  python test_master_query.py --event "Node Down"
  python test_master_query.py --device-id 5457
  python test_master_query.py --device-type "Versa"
  python test_master_query.py --message "Node Down"
  python test_master_query.py --ip 10.159.83.95 --event "Node Down"
        """
    )
    parser.add_argument("--ip",          type=str, help="Filter by IP address (exact)")
    parser.add_argument("--device",      type=str, help="Filter by device name (exact or partial with %%)")
    parser.add_argument("--event",       type=str, help="Filter by event name (e.g. 'Node Down')")
    parser.add_argument("--device-id",   type=int, help="Filter by device ID number")
    parser.add_argument("--device-type", type=str, help="Filter by device/machine type (partial match)")
    parser.add_argument("--message",     type=str, help="Filter by error message text (partial match)")

    args = parser.parse_args()

    # If no arguments provided, run a demo with all 6 input types
    if not any([args.ip, args.device, args.event, args.device_id, args.device_type, args.message]):
        print("No arguments provided. Running demo with all 6 input types:\n")

        demos = [
            {"label": "1. By IP Address",   "kwargs": {"ip": "10.159.83.95"}},
            {"label": "2. By Device Name",   "kwargs": {"device": "8395-Erlanger-KY"}},
            {"label": "3. By Event Name",    "kwargs": {"event": "EventType-7503"}},
            {"label": "4. By Device ID",     "kwargs": {"device_id": 5457}},
            {"label": "5. By Device Type",   "kwargs": {"device_type": "Versa"}},
            {"label": "6. By Error Message", "kwargs": {"message": "EventType-7503"}},
        ]

        for demo in demos:
            print(f"\n{'#' * 70}")
            print(f"  DEMO: {demo['label']}")
            print(f"{'#' * 70}")
            run_query(**demo["kwargs"])
            print()

        return

    run_query(
        ip=args.ip,
        device=args.device,
        event=args.event,
        device_id=args.device_id,
        device_type=args.device_type,
        message=args.message,
    )


if __name__ == "__main__":
    main()
