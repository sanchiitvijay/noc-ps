import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from incremental_updater import (
    clean_event_time,
    map_cross_references,
    update_events,
    update_tickets,
)


def test_site_code_mapping_links_only_equal_normalized_codes():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE devices (
            device_id INTEGER PRIMARY KEY,
            site_code TEXT,
            device_name TEXT,
            ip_address TEXT
        );
        CREATE TABLE sn_tickets (
            ticket_id INTEGER PRIMARY KEY,
            extracted_site_codes TEXT,
            extracted_device_names TEXT,
            extracted_ips TEXT
        );
        CREATE TABLE device_ticket_map (
            device_id INTEGER,
            ticket_id INTEGER,
            match_type TEXT,
            match_value TEXT,
            confidence REAL,
            UNIQUE(device_id, ticket_id, match_type)
        );
        INSERT INTO devices VALUES (1, '00123', 'device-123', '10.0.0.1');
        INSERT INTO devices VALUES (2, '00999', 'device-999', '10.0.0.2');
        """
    )
    conn.execute(
        "INSERT INTO sn_tickets VALUES (?, ?, NULL, NULL)",
        (1, json.dumps(["123"])),
    )
    conn.execute(
        "INSERT INTO sn_tickets VALUES (?, ?, NULL, NULL)",
        (2, json.dumps(["555"])),
    )

    map_cross_references(conn)

    links = conn.execute(
        "SELECT device_id, ticket_id FROM device_ticket_map WHERE match_type='site_code'"
    ).fetchall()
    assert links == [(1, 1)]


def test_event_time_preserves_source_time_without_fabricating_date():
    assert clean_event_time("[DEVICE_ID] 20:00:04.470") == "20:00:04.470"


def test_incremental_merge_preserves_source_ids_and_is_repeatable(tmp_path):
    schema_path = REPO_ROOT / "noc_database_setup 1" / "schema.sql"
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys=ON")

    event_csv = tmp_path / "events.csv"
    event_csv.write_text(
        "EventID,EventTime,EventType,Message,NodeID,DeviceName,IPAddress,MachineType,Vendor,CurrentStatus,Location\n"
        "987654321,[DEVICE_ID] 20:00:04.470,1,device down message,12345,00123-Site-CA-Edge01,10.1.2.3,Switch,Vendor,0,Site\n",
        encoding="utf-8",
    )
    ticket_csv = tmp_path / "tickets.csv"
    ticket_csv.write_text(
        "number,state,sys_created_on,sys_updated_on,closed_at,assignment_group,short_description,description,work_notes\n"
        "INC987654,Open,2026-01-01,2026-01-02,,NOC,Device issue,FEI 123 10.1.2.3 00123-Site-CA-Edge01,Investigating\n",
        encoding="utf-8",
    )

    conn.execute("BEGIN")
    update_events(conn, str(event_csv))
    update_tickets(conn, str(ticket_csv))
    map_cross_references(conn)
    conn.commit()

    assert conn.execute(
        "SELECT event_time, event_type_name FROM event_logs WHERE event_id=987654321"
    ).fetchone() == ("20:00:04.470", "Node Down")
    assert conn.execute("SELECT count(*) FROM devices").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM sn_tickets").fetchone()[0] == 1
    first_link_count = conn.execute("SELECT count(*) FROM device_ticket_map").fetchone()[0]

    conn.execute("BEGIN")
    update_events(conn, str(event_csv))
    update_tickets(conn, str(ticket_csv))
    map_cross_references(conn)
    conn.commit()

    assert conn.execute("SELECT count(*) FROM devices").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM event_logs").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM sn_tickets").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM device_ticket_map").fetchone()[0] == first_link_count