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
import random
from datetime import datetime, timedelta

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
    """
    Convert:
    '[DEVICE_ID] 20:00:04.470'
    to:
    '2026-06-28 20:00:04.470'

    Date is randomly generated between 2026-06-16 and 2026-07-16.
    """
    if pd.isna(raw_time):
        return None

    text = str(raw_time)

    # Extract time portion (HH:MM:SS.mmm)
    match = re.search(r'(\d{2}:\d{2}:\d{2}\.\d{3})', text)
    if not match:
        return None

    time_part = match.group(1)

    # Generate random date between 16-Jun-2026 and 16-Jul-2026
    start_date = datetime(2026, 6, 16)
    end_date = datetime(2026, 7, 16)

    random_days = random.randint(0, (end_date - start_date).days)
    random_date = start_date + timedelta(days=random_days)

    return f"{random_date.strftime('%Y-%m-%d')} {time_part}"

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
    return list(set(codes))

def extract_ips(text: str) -> list[str]:
    if pd.isna(text):
        return []
    ips = re.findall(r'\b((?:\d{1,3}\.){3}\d{1,3})\b', str(text))
    return list(set(ip for ip in ips if 'X' not in ip))

def extract_device_names_from_text(text: str, known_devices: set) -> list[str]:
    if pd.isna(text):
        return []
    text_str = str(text)
    return [dev for dev in known_devices if len(dev) > 5 and dev in text_str]

def log(msg: str):
    print(f"  [UPDATE] {msg}")

# ============================================================================
# INCREMENTAL UPDATE PIPELINE
# ============================================================================

def update_events(conn: sqlite3.Connection, csv_path: str) -> dict:
    print("\n" + "=" * 70)
    print(f"PHASE 1: MERGING EVENTS FROM {os.path.basename(csv_path)}")
    print("=" * 70)
    
    df = pd.read_csv(csv_path, low_memory=False)
    df['EventTime_Clean'] = df['EventTime'].apply(clean_event_time)
    
    for col in ['DeviceName', 'IPAddress', 'MachineType', 'Vendor', 'Location']:
        if col in df.columns:
            df[col] = df[col].replace({'NULL': None, 'nan': None, '': None})
            
    df['SiteCode'] = df['DeviceName'].apply(extract_site_code)
    df['SiteName'] = df['DeviceName'].apply(extract_site_name)
    
    # Update Event Types (Dynamically)
    event_types_df = df.dropna(subset=['EventType']).drop_duplicates(subset=['EventType'])
    event_type_lookup_data = []
    event_type_map = {}
    
    for _, row in event_types_df.iterrows():
        ev_id = int(row['EventType'])
        ev_name = str(row['Message']) if pd.notna(row['Message']) else f"EventType-{ev_id}"
        
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

    cursor = conn.cursor()
    cursor.executemany("""
        INSERT OR IGNORE INTO event_type_lookup (event_type_id, event_type_name, severity, category)
        VALUES (?, ?, ?, ?)
    """, event_type_lookup_data)
    
    df['EventTypeName'] = df['EventType'].map(event_type_map).fillna('Unknown')
    
    unnamed_cols = [c for c in df.columns if 'Unnamed' in str(c)]
    df['RawDetail'] = df[unnamed_cols[1] if len(unnamed_cols) > 1 else unnamed_cols[0]] if unnamed_cols else None
    
    # UPSERT Devices (Update if name and IP exist)
    devices = df.dropna(subset=['DeviceName']).groupby(['DeviceName', 'IPAddress'], dropna=False).first().reset_index()
    for _, row in devices.iterrows():
        cursor.execute("""
            INSERT INTO devices (node_id, device_name, ip_address, site_code, site_name, machine_type, vendor, location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_name, ip_address) DO UPDATE SET
                node_id = excluded.node_id,
                site_code = excluded.site_code,
                site_name = excluded.site_name,
                machine_type = excluded.machine_type,
                vendor = excluded.vendor,
                location = excluded.location;
        """, (
            int(row['NodeID']) if pd.notna(row['NodeID']) else None, row['DeviceName'], 
            row['IPAddress'] if pd.notna(row['IPAddress']) else None, row['SiteCode'], row['SiteName'],
            row['MachineType'] if pd.notna(row['MachineType']) else None, row['Vendor'] if pd.notna(row['Vendor']) else None,
            row['Location'] if pd.notna(row['Location']) else None
        ))
    conn.commit()

    device_id_map = { (dname, dip): did for did, dname, dip in cursor.execute("SELECT device_id, device_name, ip_address FROM devices").fetchall() }
    for dname, dip in list(device_id_map.keys()):
        device_id_map[dname] = device_id_map[(dname, dip)]
    
    # UPSERT Events (Update current_status if event already exists)
    batch = []
    for _, row in df.iterrows():
        if pd.isna(row.get('EventID')): continue
        dev_id = device_id_map.get((row.get('DeviceName'), row.get('IPAddress'))) or device_id_map.get(row.get('DeviceName'))
        
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
    conn.commit()
    
    return {'processed_events': len(batch)}

def update_tickets(conn: sqlite3.Connection, csv_path: str) -> dict:
    print("\n" + "=" * 70)
    print(f"PHASE 2: MERGING TICKETS FROM {os.path.basename(csv_path)}")
    print("=" * 70)
    
    df = pd.read_csv(csv_path, low_memory=False, encoding='latin-1')
    cursor = conn.cursor()
    known_devices = set(row[0] for row in cursor.execute("SELECT device_name FROM devices").fetchall())
    
    batch = []
    for _, row in df.iterrows():
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
    conn.commit()
    
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
                if any(dev_site_norm == ts.lstrip('0') or '0' for ts in json.loads(tkt_sites_json)):
                    cursor.execute("INSERT OR IGNORE INTO device_ticket_map (device_id, ticket_id, match_type, match_value, confidence) VALUES (?, ?, 'site_code', ?, 0.9)", (dev_id, tkt_id, dev_site))
            except json.JSONDecodeError: continue

    # Device Name Mapping
    all_devices = cursor.execute("SELECT device_id, device_name FROM devices WHERE device_name IS NOT NULL").fetchall()
    ticket_devs = cursor.execute("SELECT ticket_id, extracted_device_names FROM sn_tickets WHERE extracted_device_names IS NOT NULL").fetchall()
    for tkt_id, tkt_devs_json in ticket_devs:
        try:
            tkt_devs_list = json.loads(tkt_devs_json)
            for dev_id, dev_name in all_devices:
                if dev_name in tkt_devs_list:
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

    conn.commit()
    log("Cross-reference bridges created successfully.")

# ============================================================================
# RUN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Incrementally insert or update records into noc_automation.db")
    parser.add_argument("--events", type=str, help="Path to the new Event CSV", required=True)
    parser.add_argument("--tickets", type=str, help="Path to the new Tickets CSV", required=True)
    parser.add_argument("--db", type=str, default="noc_automation.db", help="Path to SQLite DB (default: noc_automation.db)")
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"Error: Database {args.db} not found. Please run the initial ETL pipeline first.")
        return

    conn = sqlite3.connect(args.db)
    
    update_events(conn, args.events)
    update_tickets(conn, args.tickets)
    map_cross_references(conn)
    
    conn.close()
    print("\n[SUCCESS] Incremental update completed.")

if __name__ == "__main__":
    main()