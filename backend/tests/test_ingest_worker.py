import asyncio

import aiosqlite
import pandas as pd

from workers.ingest_worker import (
    _detect_file_type,
    _ingest_event_logs,
    _ingest_tickets,
    _map_ticket_references,
    _read_csv,
)


def test_detect_file_type_accepts_original_source_headers():
    events = pd.DataFrame(columns=[
        "EventID", "EventTime", "EventType", "Message", "DeviceName",
    ])
    tickets = pd.DataFrame(columns=["number", "short_description", "state"])

    assert _detect_file_type(events) == "event_log"
    assert _detect_file_type(tickets) == "ticket"


def test_ticket_csv_reader_falls_back_to_windows_1252():
    csv_bytes = b"number,short_description,state\nINC987654,Link\x97down,Open\n"

    frame = _read_csv(csv_bytes)

    assert frame.loc[0, "short_description"] == "Link\u2014down"


def test_source_exports_preserve_event_ids_and_build_ticket_links():
    async def exercise():
        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row
        await conn.executescript(
            """
            CREATE TABLE devices (
                device_id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER, device_name TEXT NOT NULL, ip_address TEXT,
                site_code TEXT, site_name TEXT, machine_type TEXT, vendor TEXT,
                location TEXT, UNIQUE(device_name, ip_address)
            );
            CREATE TABLE event_type_lookup (
                event_type_id INTEGER PRIMARY KEY, event_type_name TEXT NOT NULL,
                severity TEXT, category TEXT
            );
            CREATE TABLE event_logs (
                event_id INTEGER PRIMARY KEY, event_time TEXT, event_type_id INTEGER,
                event_type_name TEXT, message TEXT, device_id INTEGER,
                current_status INTEGER, raw_detail TEXT
            );
            CREATE TABLE sn_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_number TEXT UNIQUE,
                ticket_type TEXT, state TEXT, created_on TEXT, updated_on TEXT,
                closed_at TEXT, assignment_group TEXT, short_description TEXT,
                description TEXT, work_notes TEXT, extracted_site_codes TEXT,
                extracted_ips TEXT, extracted_device_names TEXT
            );
            CREATE TABLE device_ticket_map (
                device_id INTEGER, ticket_id INTEGER, match_type TEXT,
                match_value TEXT, confidence REAL,
                UNIQUE(device_id, ticket_id, match_type)
            );
            """
        )
        await conn.execute(
            """INSERT INTO devices
               (node_id, device_name, ip_address, site_code, site_name,
                machine_type, vendor, location)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (12345, "00123-Site-CA-Edge01 ", "10.1.2.3", "00123", "Site-CA", "Switch", "Vendor", "Site"),
        )
        await conn.commit()

        event_rows = pd.DataFrame([{
            "EventID": "987654321",
            "EventTime": "[DEVICE_ID] 20:00:04.470",
            "EventType": "5000",
            "Message": "device down message",
            "NodeID": "12345",
            "DeviceName": "00123-Site-CA-Edge01",
            "IPAddress": "10.1.2.3",
            "MachineType": "Switch",
            "Vendor": "Vendor",
            "CurrentStatus": "0",
            "Location": "Site",
        }, {
            "EventID": "987654322",
            "EventTime": "[DEVICE_ID] 20:00:05.470",
            "EventType": "5000",
            "Message": "unlinked device event",
            "NodeID": None,
            "DeviceName": None,
            "IPAddress": None,
            "MachineType": None,
            "Vendor": None,
            "CurrentStatus": "0",
            "Location": None,
        }])
        assert await _ingest_event_logs(conn, event_rows) == 2
        cursor = await conn.execute("SELECT COUNT(*) FROM devices")
        assert (await cursor.fetchone())[0] == 1

        cursor = await conn.execute(
            "SELECT event_id, event_time, event_type_id, device_id FROM event_logs ORDER BY event_id"
        )
        events = await cursor.fetchall()
        assert [tuple(event) for event in events] == [
            (987654321, "20:00:04.470", 5000, 1),
            (987654322, "20:00:05.470", 5000, None),
        ]

        ticket_rows = pd.DataFrame([{
            "number": "INC987654",
            "state": "Open",
            "sys_created_on": "2026-01-01",
            "sys_updated_on": "2026-01-02",
            "short_description": "Device issue",
            "description": "FEI 123 10.1.2.3 00123-Site-CA-Edge01",
            "work_notes": "Investigating",
        }])
        assert await _ingest_tickets(conn, ticket_rows) == 1
        await _map_ticket_references(conn)

        cursor = await conn.execute(
            "SELECT DISTINCT match_type FROM device_ticket_map ORDER BY match_type"
        )
        assert [row[0] for row in await cursor.fetchall()] == [
            "device_name", "ip_address", "site_code",
        ]
        await conn.close()

    asyncio.run(exercise())