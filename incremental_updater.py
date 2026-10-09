"""
NOC Automation - Incremental ETL Updater
========================================
Parses new or updated CSV files and merges them into the existing database.
Existing tickets will update their state and work_notes. 
Existing events will update their current_status.
New device-ticket cross-references will be generated.
"""

import pandas as pd
import sqlite3
import re
import json
import os
import argparse
from pathlib import Path
import sys

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_site_code(device_name: str) -> str | None:
    if pd.isna(device_name) or device_name in ('NULL', 'nan', ''):
        return None
    match = re.match(r'^(\d{3,5})', str(device_name))
    return match.group(1) if match else None

def extract_site_name(device_name: str) -> str | None:
    if pd.isna(device_name) or device_name in ('NULL', 'nan', ''):
        return None
    match = re.match(r'^\d{3,5}[-_]([A-Za-z][\w-]*(?:-[A-Z]{2})?)(?:[-_]|$)', str(device_name))
    return match.group(1) if match else None

# def clean_event_time(raw_time: str) -> str | None:
#     if pd.isna(raw_time):
#         return None
#     cleaned = re.sub(r'^\[DEVICE_ID\]\s*', '', str(raw_time)).strip()
#     return cleaned if cleaned else None


def clean_event_time(raw_time: str) -> str | None:
    """Strip the device marker while preserving the source time-of-day value."""
    if pd.isna(raw_time):
        return None
    cleaned = re.sub(r'^\[DEVICE_ID\]\s*', '', str(raw_time)).strip()
    return cleaned or None

def extract_ticket_type(ticket_number: str) -> str | None:
    if pd.isna(ticket_number):
        return None
    for prefix in ('RITM', 'TASK', 'INC', 'CHG'):
        if str(ticket_number).startswith(prefix):
            return prefix
    return None

def extract_fei_codes(text: str) -> list[str]:
    if pd.isna(text):
        return []
    codes = re.findall(r'FEI[\s:|\-]*(\d{3,5})', str(text), re.IGNORECASE)
    return sorted(set(codes))

def extract_ips(text: str) -> list[str]:
    if pd.isna(text):
        return []
    ips = re.findall(r'\b((?:\d{1,3}\.){3}\d{1,3})\b', str(text))
    return sorted(set(ip for ip in ips if 'X' not in ip))

def extract_device_names_from_text(text: str, known_devices: set) -> list[str]:
    if pd.isna(text):
        return []
    text_str = str(text)
    return sorted(dev for dev in known_devices if len(dev) > 5 and dev in text_str)

def log(msg: str):
    print(f"  [UPDATE] {msg}")


def configured_database_path() -> Path:
    """Resolve the same SQLite target as the backend configuration."""
    backend_dir = Path(__file__).resolve().parent / 'backend'
    sys.path.insert(0, str(backend_dir))
    from config import Settings  # noqa: PLC0415

    settings = Settings(_env_file=backend_dir / '.env')
    db_path = Path(settings.db_path)
    return db_path if db_path.is_absolute() else backend_dir / db_path

# ============================================================================
# INCREMENTAL UPDATE PIPELINE
# ============================================================================

def update_events(conn: sqlite3.Connection, csv_path: str) -> dict:
    print("\n" + "=" * 70)
    print(f"PHASE 1: MERGING EVENTS FROM {os.path.basename(csv_path)}")
    print("=" * 70)
    
    df = pd.read_csv(csv_path, low_memory=False)
    required_columns = {
        'EventID', 'EventTime', 'EventType', 'Message', 'NodeID',
        'DeviceName', 'CurrentStatus',
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Event CSV is missing required columns: {', '.join(sorted(missing_columns))}"
        )

    for col in ['IPAddress', 'MachineType', 'Vendor', 'Location']:
        if col not in df.columns:
            df[col] = None
    df['EventTime_Clean'] = df['EventTime'].apply(clean_event_time)
    
    for col in ['DeviceName', 'IPAddress', 'MachineType', 'Vendor', 'Location']:
        if col in df.columns:
            df[col] = df[col].replace({'NULL': None, 'nan': None, '': None})
            
    df['SiteCode'] = df['DeviceName'].apply(extract_site_code)
    df['SiteName'] = df['DeviceName'].apply(extract_site_name)
    
    # Update Event Types (Dynamically)
    cursor = conn.cursor()
    existing_event_types = dict(cursor.execute(
        "SELECT event_type_id, event_type_name FROM event_type_lookup"
    ).fetchall())
    event_types_df = df.dropna(subset=['EventType']).drop_duplicates(subset=['EventType'])
    event_type_lookup_data = []
    event_type_map = {}
    
    for _, row in event_types_df.iterrows():
        ev_id = int(row['EventType'])
        supplied_name = row.get('EventTypeName')
        ev_name = (
            str(supplied_name).strip()
            if pd.notna(supplied_name) and str(supplied_name).strip()
            else existing_event_types.get(ev_id, f"EventType-{ev_id}")
        )
        
        severity = 'P4'
        category = 'other'
        ev_name_lower = ev_name.lower()
        
        if 'node down' in ev_name_lower or ev_id in (5000, 5001):
            severity = 'P1'
            category = 'connectivity'
        elif 'node up' in ev_name_lower:
            severity = 'P3'
            category = 'connectivity'
        elif 'interface' in ev_name_lower:
            severity = 'P2'
            category = 'interface'
            if 'up' in ev_name_lower:
                severity = 'P3'
        elif ev_id in (529, 3805):
            category = 'performance'
        elif ev_id == 604:
            category = 'wireless'
            
        event_type_lookup_data.append((ev_id, ev_name, severity, category))
        event_type_map[ev_id] = ev_name

    cursor.executemany("""
        INSERT OR IGNORE INTO event_type_lookup (event_type_id, event_type_name, severity, category)
        VALUES (?, ?, ?, ?)
    """, event_type_lookup_data)
    
    event_type_ids = pd.to_numeric(df['EventType'], errors='coerce')
    df['EventTypeName'] = event_type_ids.map(event_type_map).fillna('Unknown')
    
    unnamed_cols = [c for c in df.columns if 'Unnamed' in str(c)]
    df['RawDetail'] = df[unnamed_cols[1] if len(unnamed_cols) > 1 else unnamed_cols[0]] if unnamed_cols else None
    
    # UPSERT Devices (Update if name and IP exist)
    devices = df.dropna(subset=['DeviceName']).groupby(['DeviceName', 'IPAddress'], dropna=False).first().reset_index()
    for _, row in devices.iterrows():
        ip_address = row['IPAddress'] if pd.notna(row['IPAddress']) else None
        values = (
            int(row['NodeID']) if pd.notna(row['NodeID']) else None,
            row['SiteCode'], row['SiteName'],
            row['MachineType'] if pd.notna(row['MachineType']) else None,
            row['Vendor'] if pd.notna(row['Vendor']) else None,
            row['Location'] if pd.notna(row['Location']) else None,
        )
        existing = cursor.execute(
            "SELECT device_id FROM devices WHERE TRIM(device_name) = TRIM(?) AND ip_address IS ?",
            (row['DeviceName'], ip_address),
        ).fetchone()
        if existing:
            cursor.execute(
                """UPDATE devices SET node_id=?, site_code=?, site_name=?, machine_type=?,
                   vendor=?, location=? WHERE device_id=?""",
                (*values, existing[0]),
            )
        else:
            cursor.execute(
                """INSERT INTO devices
                   (node_id, device_name, ip_address, site_code, site_name,
                    machine_type, vendor, location)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (values[0], row['DeviceName'], ip_address, *values[1:]),
            )

    device_id_map = {}
    for did, dname, dip in cursor.execute(
        "SELECT device_id, device_name, ip_address FROM devices"
    ).fetchall():
        device_id_map[(dname, dip)] = did
        device_id_map[(dname.strip(), dip)] = did
        device_id_map.setdefault(dname.strip(), did)
    
    # UPSERT Events (Update current_status if event already exists)
    batch = []
    for _, row in df.iterrows():
        if pd.isna(row.get('EventID')): continue
        ip_address = row.get('IPAddress')
        ip_address = None if pd.isna(ip_address) else ip_address
        device_name = row.get('DeviceName')
        device_name = device_name.strip() if isinstance(device_name, str) else device_name
        dev_id = device_id_map.get((device_name, ip_address)) or device_id_map.get(device_name)
        
        batch.append((
            int(row['EventID']), row.get('EventTime_Clean'),
            int(row['EventType']) if pd.notna(row.get('EventType')) else None,
            row.get('EventTypeName'), row.get('Message'), dev_id,
            int(row['CurrentStatus']) if pd.notna(row.get('CurrentStatus')) else None,
            row.get('RawDetail') if pd.notna(row.get('RawDetail')) else None
        ))
    
    cursor.executemany("""
        INSERT INTO event_logs (event_id, event_time, event_type_id, event_type_name, message, device_id, current_status, raw_detail)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET current_status = excluded.current_status;
    """, batch)
    
    return {'processed_events': len(batch)}

def update_tickets(conn: sqlite3.Connection, csv_path: str) -> dict:
    print("\n" + "=" * 70)
    print(f"PHASE 2: MERGING TICKETS FROM {os.path.basename(csv_path)}")
    print("=" * 70)
    
    df = pd.read_csv(csv_path, low_memory=False, encoding='latin-1')
    if 'number' not in df.columns:
        raise ValueError("Ticket CSV is missing required column: number")

    cursor = conn.cursor()
    known_devices = {
        row[0].strip()
        for row in cursor.execute("SELECT device_name FROM devices").fetchall()
    }
    
    batch = []
    for _, row in df.iterrows():
        if pd.isna(row.get('number')):
            continue
        all_text = f"{row.get('short_description', '')} {row.get('description', '')} {row.get('work_notes', '')}"
        fei_codes = extract_fei_codes(all_text)
        ips = extract_ips(all_text)
        dev_names = extract_device_names_from_text(all_text, known_devices)
        
        batch.append((
            row['number'], extract_ticket_type(row['number']), row.get('state'),
            row.get('sys_created_on'), row.get('sys_updated_on'), 
            row.get('closed_at') if pd.notna(row.get('closed_at')) else None,
            row.get('assignment_group'), row.get('short_description'),
            row.get('description') if pd.notna(row.get('description')) else None,
            row.get('work_notes') if pd.notna(row.get('work_notes')) else None,
            json.dumps(fei_codes) if fei_codes else None,
            json.dumps(ips) if ips else None, json.dumps(dev_names) if dev_names else None
        ))
    
    # UPSERT Tickets (Update states, timestamps, and notes on existing tickets)
    cursor.executemany("""
        INSERT INTO sn_tickets (ticket_number, ticket_type, state, created_on, updated_on, closed_at, assignment_group, short_description, description, work_notes, extracted_site_codes, extracted_ips, extracted_device_names)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticket_number) DO UPDATE SET
            state = excluded.state,
            updated_on = excluded.updated_on,
            closed_at = excluded.closed_at,
            work_notes = excluded.work_notes,
            assignment_group = excluded.assignment_group,
            extracted_site_codes = excluded.extracted_site_codes,
            extracted_ips = excluded.extracted_ips,
            extracted_device_names = excluded.extracted_device_names;
    """, batch)
    
    return {'processed_tickets': len(batch)}

def map_cross_references(conn: sqlite3.Connection):
    print("\n" + "=" * 70)
    print("PHASE 3: UPDATING CROSS-REFERENCE MAPPING")
    print("=" * 70)
    
    cursor = conn.cursor()
    
    # Site Code Mapping
    device_sites = cursor.execute("SELECT device_id, site_code FROM devices WHERE site_code IS NOT NULL").fetchall()
    ticket_sites = cursor.execute("SELECT ticket_id, extracted_site_codes FROM sn_tickets WHERE extracted_site_codes IS NOT NULL").fetchall()
    for dev_id, dev_site in device_sites:
        dev_site_norm = dev_site.lstrip('0') or '0'
        for tkt_id, tkt_sites_json in ticket_sites:
            try:
                ticket_sites_norm = {
                    str(site).lstrip('0') or '0'
                    for site in json.loads(tkt_sites_json)
                }
                if dev_site_norm in ticket_sites_norm:
                    cursor.execute("INSERT OR IGNORE INTO device_ticket_map (device_id, ticket_id, match_type, match_value, confidence) VALUES (?, ?, 'site_code', ?, 0.9)", (dev_id, tkt_id, dev_site))
            except json.JSONDecodeError: continue

    # Device Name Mapping
    all_devices = cursor.execute("SELECT device_id, device_name FROM devices WHERE device_name IS NOT NULL").fetchall()
    ticket_devs = cursor.execute("SELECT ticket_id, extracted_device_names FROM sn_tickets WHERE extracted_device_names IS NOT NULL").fetchall()
    for tkt_id, tkt_devs_json in ticket_devs:
        try:
            tkt_devs_list = json.loads(tkt_devs_json)
            for dev_id, dev_name in all_devices:
                if dev_name.strip() in tkt_devs_list:
                    cursor.execute("INSERT OR IGNORE INTO device_ticket_map (device_id, ticket_id, match_type, match_value, confidence) VALUES (?, ?, 'device_name', ?, 0.8)", (dev_id, tkt_id, dev_name))
        except json.JSONDecodeError: continue

    # IP Address Mapping
    device_ips = cursor.execute("SELECT device_id, ip_address FROM devices WHERE ip_address IS NOT NULL").fetchall()
    ticket_ips = cursor.execute("SELECT ticket_id, extracted_ips FROM sn_tickets WHERE extracted_ips IS NOT NULL").fetchall()
    ip_to_devices = {}
    for dev_id, dev_ip in device_ips: ip_to_devices.setdefault(dev_ip, []).append(dev_id)
    
    for tkt_id, tkt_ips_json in ticket_ips:
        try:
            for tip in json.loads(tkt_ips_json):
                if tip in ip_to_devices:
                    for dev_id in ip_to_devices[tip]:
                        cursor.execute("INSERT OR IGNORE INTO device_ticket_map (device_id, ticket_id, match_type, match_value, confidence) VALUES (?, ?, 'ip_address', ?, 0.7)", (dev_id, tkt_id, tip))
        except json.JSONDecodeError: continue

    log("Cross-reference bridges created successfully.")

# ============================================================================
# RUN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Incrementally update the configured NOC SQLite database")
    parser.add_argument("--events", type=str, help="Path to the new Event CSV", required=True)
    parser.add_argument("--tickets", type=str, help="Path to the new Tickets CSV", required=True)
    parser.add_argument("--db", type=str, help="Override the SQLite database configured by the backend")
    args = parser.parse_args()

    for input_path in (args.events, args.tickets):
        if not Path(input_path).is_file():
            parser.error(f"Input file not found: {input_path}")

    db_path = Path(args.db) if args.db else configured_database_path()
    if not db_path.is_file():
        parser.error(f"Database {db_path} not found. Run the initial ETL pipeline first.")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        event_stats = update_events(conn, args.events)
        ticket_stats = update_tickets(conn, args.tickets)
        map_cross_references(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"\n[SUCCESS] Incremental update completed for {db_path}.")
    print(f"Events processed: {event_stats['processed_events']}")
    print(f"Tickets processed: {ticket_stats['processed_tickets']}")

if __name__ == "__main__":
    main()