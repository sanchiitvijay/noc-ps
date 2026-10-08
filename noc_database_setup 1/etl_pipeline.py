"""
NOC Automation ETL Pipeline
============================
Extracts data from CSV files, transforms/cleans it, and loads into SQLite database.

Usage:
    python etl_pipeline.py --error-csv <path> --ticket-csv <path> --db-path <path> --schema-sql <path>

"""

import pandas as pd
import sqlite3
import re
import json
import os
import sys
import argparse
from pathlib import Path

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
    if match:
        return match.group(1)
    return None


def clean_event_time(raw_time: str) -> str | None:
    if pd.isna(raw_time):
        return None
    cleaned = re.sub(r'^\[DEVICE_ID\]\s*', '', str(raw_time)).strip()
    return cleaned if cleaned else None


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
    found = []
    for dev in known_devices:
        if len(dev) > 5 and dev in text_str:
            found.append(dev)
    return found


def log(msg: str):
    print(f"  [ETL] {msg}")


# ============================================================================
# ETL PHASE 1: EXTRACT & CLEAN EVENT LOGS
# ============================================================================

def etl_events(conn: sqlite3.Connection, event_csv: Path) -> dict:
    print("\n" + "=" * 70)
    print("PHASE 1: EVENT LOGS ETL")
    print("=" * 70)
    
    log("Loading CSV...")
    df = pd.read_csv(event_csv, low_memory=False)
    log(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    
    log("Cleaning EventTime (removing [DEVICE_ID] prefix)...")
    df['EventTime_Clean'] = df['EventTime'].apply(clean_event_time)
    cleaned_count = df['EventTime_Clean'].notna().sum()
    log(f"  Cleaned {cleaned_count}/{len(df)} timestamps")
    
    log("Replacing string NULLs...")
    for col in ['DeviceName', 'IPAddress', 'MachineType', 'Vendor', 'Location']:
        if col in df.columns:
            df[col] = df[col].replace({'NULL': None, 'nan': None, '': None})
    
    log("Extracting site codes from DeviceName...")
    df['SiteCode'] = df['DeviceName'].apply(extract_site_code)
    df['SiteName'] = df['DeviceName'].apply(extract_site_name)
    site_count = df['SiteCode'].notna().sum()
    log(f"  Extracted {df['SiteCode'].nunique()} unique site codes from {site_count} rows")
    
    event_type_map = {
        1: 'Node Down', 5: 'Node Up', 10: 'Interface Down', 11: 'Interface Up',
        14: 'EventType-14', 19: 'Interface Status Changed',
        51: 'EventType-51', 52: 'EventType-52', 58: 'EventType-58',
        524: 'EventType-524', 529: 'EventType-529', 604: 'EventType-604',
        3805: 'EventType-3805', 5000: 'EventType-5000', 5001: 'EventType-5001',
        6808: 'EventType-6808'
    }
    df['EventTypeName'] = df['EventType'].map(event_type_map).fillna('Unknown')
    
    unnamed_cols = [c for c in df.columns if 'Unnamed' in str(c)]
    if unnamed_cols and len(unnamed_cols) > 1:
        detail_col = unnamed_cols[1] if len(unnamed_cols) > 1 else unnamed_cols[0]
        df['RawDetail'] = df[detail_col]
    else:
        df['RawDetail'] = None
    
    log("Building device registry...")
    devices = df.dropna(subset=['DeviceName']).groupby(
        ['DeviceName', 'IPAddress'], dropna=False
    ).agg({
        'NodeID': 'first',
        'SiteCode': 'first',
        'SiteName': 'first',
        'MachineType': 'first',
        'Vendor': 'first',
        'Location': 'first'
    }).reset_index()
    
    log(f"  Found {len(devices)} unique device records")
    
    log("Loading devices into database...")
    device_id_map = {}
    cursor = conn.cursor()
    for _, row in devices.iterrows():
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO devices 
                    (node_id, device_name, ip_address, site_code, site_name, 
                     machine_type, vendor, location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['NodeID']) if pd.notna(row['NodeID']) else None,
                row['DeviceName'],
                row['IPAddress'] if pd.notna(row['IPAddress']) else None,
                row['SiteCode'],
                row['SiteName'],
                row['MachineType'] if pd.notna(row['MachineType']) else None,
                row['Vendor'] if pd.notna(row['Vendor']) else None,
                row['Location'] if pd.notna(row['Location']) else None
            ))
        except Exception as e:
            pass
    conn.commit()
    
    cursor.execute("SELECT device_id, device_name, ip_address FROM devices")
    for did, dname, dip in cursor.fetchall():
        device_id_map[(dname, dip)] = did
        device_id_map[dname] = did
    
    device_count = cursor.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    log(f"  Loaded {device_count} devices into database")
    
    log("Loading event logs into database...")
    batch = []
    skipped = 0
    for _, row in df.iterrows():
        eid = row.get('EventID')
        if pd.isna(eid):
            skipped += 1
            continue
            
        dev_name = row.get('DeviceName')
        dev_ip = row.get('IPAddress')
        dev_id = device_id_map.get((dev_name, dev_ip)) or device_id_map.get(dev_name)
        
        batch.append((
            int(eid),
            row.get('EventTime_Clean'),
            int(row['EventType']) if pd.notna(row.get('EventType')) else None,
            row.get('EventTypeName'),
            row.get('Message'),
            dev_id,
            int(row['CurrentStatus']) if pd.notna(row.get('CurrentStatus')) else None,
            row.get('RawDetail') if pd.notna(row.get('RawDetail')) else None
        ))
    
    cursor.executemany("""
        INSERT OR IGNORE INTO event_logs 
            (event_id, event_time, event_type_id, event_type_name, message,
             device_id, current_status, raw_detail)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    conn.commit()
    
    event_count = cursor.execute("SELECT COUNT(*) FROM event_logs").fetchone()[0]
    log(f"  Loaded {event_count} events (skipped {skipped} rows with no EventID)")
    
    stats = {
        'total_rows': len(df),
        'devices_loaded': device_count,
        'events_loaded': event_count,
        'site_codes_found': df['SiteCode'].nunique(),
        'skipped': skipped
    }
    
    return stats


# ============================================================================
# ETL PHASE 2: EXTRACT & CLEAN SERVICENOW TICKETS
# ============================================================================

def etl_tickets(conn: sqlite3.Connection, ticket_csv: Path) -> dict:
    print("\n" + "=" * 70)
    print("PHASE 2: SERVICENOW TICKETS ETL")
    print("=" * 70)
    
    log("Loading CSV (latin-1 encoding)...")
    df = pd.read_csv(ticket_csv, low_memory=False, encoding='latin-1')
    log(f"Loaded {len(df)} tickets, {len(df.columns)} columns")
    
    cursor = conn.cursor()
    cursor.execute("SELECT device_name FROM devices")
    known_devices = set(row[0] for row in cursor.fetchall())
    log(f"  Using {len(known_devices)} known device names for matching")
    
    log("Processing tickets: extracting FEI codes, IPs, device names...")
    batch = []
    for _, row in df.iterrows():
        all_text = ' '.join([
            str(row.get('short_description', '') or ''),
            str(row.get('description', '') or ''),
            str(row.get('work_notes', '') or '')
        ])
        
        fei_codes = extract_fei_codes(all_text)
        ips = extract_ips(all_text)
        dev_names = extract_device_names_from_text(all_text, known_devices)
        
        ticket_type = extract_ticket_type(row['number'])
        
        batch.append((
            row['number'],
            ticket_type,
            row.get('state'),
            row.get('sys_created_on'),
            row.get('sys_updated_on'),
            row.get('closed_at') if pd.notna(row.get('closed_at')) else None,
            row.get('assignment_group'),
            row.get('short_description'),
            row.get('description') if pd.notna(row.get('description')) else None,
            row.get('work_notes') if pd.notna(row.get('work_notes')) else None,
            json.dumps(fei_codes) if fei_codes else None,
            json.dumps(ips) if ips else None,
            json.dumps(dev_names) if dev_names else None
        ))
    
    cursor.executemany("""
        INSERT OR IGNORE INTO sn_tickets
            (ticket_number, ticket_type, state, created_on, updated_on, closed_at,
             assignment_group, short_description, description, work_notes,
             extracted_site_codes, extracted_ips, extracted_device_names)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch)
    conn.commit()
    
    ticket_count = cursor.execute("SELECT COUNT(*) FROM sn_tickets").fetchone()[0]
    log(f"  Loaded {ticket_count} tickets")
    
    fei_tickets = cursor.execute(
        "SELECT COUNT(*) FROM sn_tickets WHERE extracted_site_codes IS NOT NULL"
    ).fetchone()[0]
    ip_tickets = cursor.execute(
        "SELECT COUNT(*) FROM sn_tickets WHERE extracted_ips IS NOT NULL"
    ).fetchone()[0]
    dev_tickets = cursor.execute(
        "SELECT COUNT(*) FROM sn_tickets WHERE extracted_device_names IS NOT NULL"
    ).fetchone()[0]
    
    log(f"  Tickets with FEI codes: {fei_tickets}")
    log(f"  Tickets with IPs: {ip_tickets}")
    log(f"  Tickets with device names: {dev_tickets}")
    
    return {
        'tickets_loaded': ticket_count,
        'with_fei': fei_tickets,
        'with_ips': ip_tickets,
        'with_devices': dev_tickets
    }


# ============================================================================
# ETL PHASE 3: BUILD CROSS-REFERENCE MAP
# ============================================================================

def etl_crossref(conn: sqlite3.Connection) -> dict:
    print("\n" + "=" * 70)
    print("PHASE 3: CROSS-REFERENCE MAPPING")
    print("=" * 70)
    
    cursor = conn.cursor()
    total_links = 0
    
    log("Strategy 1: Matching by FEI/Site Code (confidence: 0.9)...")
    cursor.execute("SELECT device_id, site_code FROM devices WHERE site_code IS NOT NULL")
    device_sites = cursor.fetchall()
    
    cursor.execute("SELECT ticket_id, extracted_site_codes FROM sn_tickets WHERE extracted_site_codes IS NOT NULL")
    ticket_sites = cursor.fetchall()
    
    site_matches = 0
    for dev_id, dev_site in device_sites:
        for tkt_id, tkt_sites_json in ticket_sites:
            try:
                tkt_sites = json.loads(tkt_sites_json)
            except (json.JSONDecodeError, TypeError):
                continue
            
            dev_site_normalized = dev_site.lstrip('0') or '0'
            for ts in tkt_sites:
                ts_normalized = ts.lstrip('0') or '0'
                if dev_site_normalized == ts_normalized:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO device_ticket_map
                                (device_id, ticket_id, match_type, match_value, confidence)
                            VALUES (?, ?, 'site_code', ?, 0.9)
                        """, (dev_id, tkt_id, dev_site))
                        site_matches += 1
                    except:
                        pass
    
    conn.commit()
    log(f"  Site code matches: {site_matches}")
    total_links += site_matches
    
    log("Strategy 2: Matching by Device Name (confidence: 0.8)...")
    cursor.execute("SELECT device_id, device_name FROM devices WHERE device_name IS NOT NULL")
    all_devices = cursor.fetchall()
    
    cursor.execute("SELECT ticket_id, extracted_device_names FROM sn_tickets WHERE extracted_device_names IS NOT NULL")
    ticket_devs = cursor.fetchall()
    
    name_matches = 0
    for tkt_id, tkt_devs_json in ticket_devs:
        try:
            tkt_devs = json.loads(tkt_devs_json)
        except (json.JSONDecodeError, TypeError):
            continue
        
        for dev_id, dev_name in all_devices:
            if dev_name in tkt_devs:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO device_ticket_map
                            (device_id, ticket_id, match_type, match_value, confidence)
                        VALUES (?, ?, 'device_name', ?, 0.8)
                    """, (dev_id, tkt_id, dev_name))
                    name_matches += 1
                except:
                    pass
    
    conn.commit()
    log(f"  Device name matches: {name_matches}")
    total_links += name_matches
    
    log("Strategy 3: Matching by IP Address (confidence: 0.7)...")
    cursor.execute("SELECT device_id, ip_address FROM devices WHERE ip_address IS NOT NULL")
    device_ips = cursor.fetchall()
    
    cursor.execute("SELECT ticket_id, extracted_ips FROM sn_tickets WHERE extracted_ips IS NOT NULL")
    ticket_ips = cursor.fetchall()
    
    ip_matches = 0
    ip_to_devices = {}
    for dev_id, dev_ip in device_ips:
        ip_to_devices.setdefault(dev_ip, []).append(dev_id)
    
    for tkt_id, tkt_ips_json in ticket_ips:
        try:
            tkt_ips = json.loads(tkt_ips_json)
        except (json.JSONDecodeError, TypeError):
            continue
        
        for tip in tkt_ips:
            if tip in ip_to_devices:
                for dev_id in ip_to_devices[tip]:
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO device_ticket_map
                                (device_id, ticket_id, match_type, match_value, confidence)
                            VALUES (?, ?, 'ip_address', ?, 0.7)
                        """, (dev_id, tkt_id, tip))
                        ip_matches += 1
                    except:
                        pass
    
    conn.commit()
    log(f"  IP address matches: {ip_matches}")
    total_links += ip_matches
    
    final_count = cursor.execute("SELECT COUNT(*) FROM device_ticket_map").fetchone()[0]
    unique_devices = cursor.execute(
        "SELECT COUNT(DISTINCT device_id) FROM device_ticket_map"
    ).fetchone()[0]
    unique_tickets = cursor.execute(
        "SELECT COUNT(DISTINCT ticket_id) FROM device_ticket_map"
    ).fetchone()[0]
    
    log(f"\n  TOTAL cross-reference links: {final_count}")
    log(f"  Unique devices linked: {unique_devices}")
    log(f"  Unique tickets linked: {unique_tickets}")
    
    return {
        'total_links': final_count,
        'site_matches': site_matches,
        'name_matches': name_matches,
        'ip_matches': ip_matches,
        'devices_linked': unique_devices,
        'tickets_linked': unique_tickets
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="NOC Automation ETL Pipeline")
    parser.add_argument("--error-csv", required=True, type=Path, help="Path to the error (events) CSV file")
    parser.add_argument("--ticket-csv", required=True, type=Path, help="Path to the ServiceNow ticket CSV file")
    parser.add_argument("--db-path", required=True, type=Path, help="Path to output SQLite database")
    parser.add_argument("--schema-sql", required=True, type=Path, help="Path to schema.sql")
    args = parser.parse_args()

    print("=" * 70)
    print("  NOC AUTOMATION - ETL PIPELINE")
    print("  Building database from CSV sources...")
    print("=" * 70)
    
    if not args.error_csv.exists():
        print(f"ERROR: Error CSV not found: {args.error_csv}")
        sys.exit(1)
    if not args.ticket_csv.exists():
        print(f"ERROR: Ticket CSV not found: {args.ticket_csv}")
        sys.exit(1)
    
    if args.db_path.exists():
        log(f"Removing existing database: {args.db_path}")
        os.remove(args.db_path)
    
    log(f"Creating database: {args.db_path}")
    conn = sqlite3.Connection(str(args.db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    
    log("Executing schema.sql...")
    if args.schema_sql.exists():
        with open(args.schema_sql, 'r') as f:
            conn.executescript(f.read())
        log("  Schema created successfully")
    else:
        print(f"WARNING: schema.sql not found at {args.schema_sql}, creating inline...")
    
    event_stats = etl_events(conn, args.error_csv)
    ticket_stats = etl_tickets(conn, args.ticket_csv)
    crossref_stats = etl_crossref(conn)
    
    conn.execute("PRAGMA foreign_keys=ON")
    
    print("\n" + "=" * 70)
    print("  ETL PIPELINE COMPLETE - SUMMARY")
    print("=" * 70)
    print(f"\n  Database: {args.db_path}")
    print(f"  Size: {args.db_path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"\n  Events:")
    print(f"    Source rows:    {event_stats['total_rows']:,}")
    print(f"    Devices loaded: {event_stats['devices_loaded']:,}")
    print(f"    Events loaded:  {event_stats['events_loaded']:,}")
    print(f"    Site codes:     {event_stats['site_codes_found']}")
    print(f"\n  Tickets:")
    print(f"    Tickets loaded: {ticket_stats['tickets_loaded']}")
    print(f"    With FEI codes: {ticket_stats['with_fei']}")
    print(f"    With IPs:       {ticket_stats['with_ips']}")
    print(f"    With devices:   {ticket_stats['with_devices']}")
    print(f"\n  Cross-References:")
    print(f"    Total links:    {crossref_stats['total_links']}")
    print(f"    By site code:   {crossref_stats['site_matches']}")
    print(f"    By device name: {crossref_stats['name_matches']}")
    print(f"    By IP address:  {crossref_stats['ip_matches']}")
    print(f"    Devices linked: {crossref_stats['devices_linked']}")
    print(f"    Tickets linked: {crossref_stats['tickets_linked']}")
    
    conn.close()
    print(f"\n  Database ready at: {args.db_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
