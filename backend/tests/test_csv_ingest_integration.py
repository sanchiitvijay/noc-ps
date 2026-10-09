"""
Integration tests for CSV ingestion using realistic fixture files.

Exercises the full pipeline: _read_csv → _detect_file_type →
_ingest_event_logs / _ingest_tickets → _map_ticket_references
with CSV files that mirror the actual source export format
(30_Days_EventTypeName_device_name_ANONYMIZED.csv and
SN_Tickets_NOC_anonymized.csv).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite
import pandas as pd
import pytest

from workers.ingest_worker import (
    _detect_file_type,
    _ingest_event_logs,
    _ingest_tickets,
    _map_ticket_references,
    _read_csv,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAKE_EVENTS_CSV = FIXTURES / "fake_events.csv"
FAKE_TICKETS_CSV = FIXTURES / "fake_tickets.csv"

# ---------------------------------------------------------------------------
# Schema — matches the test schema used by test_ingest_worker.py
# (worker functions use INTEGER AUTOINCREMENT for device_id/ticket_id)
# ---------------------------------------------------------------------------

_SCHEMA_DDL = """\
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


# ---------------------------------------------------------------------------
# Tests — CSV reading & file type detection
# ---------------------------------------------------------------------------


class TestReadCsvFixtures:
    """Verify _read_csv can parse the realistic fixture files."""

    def test_read_events_csv(self):
        raw = FAKE_EVENTS_CSV.read_bytes()
        df = _read_csv(raw)
        assert len(df) == 12
        # Verify original source column names are present
        assert "EventID" in df.columns
        assert "EventTime" in df.columns
        assert "DeviceName" in df.columns
        assert "NodeID" in df.columns

    def test_read_tickets_csv(self):
        raw = FAKE_TICKETS_CSV.read_bytes()
        df = _read_csv(raw)
        assert len(df) == 7
        # Verify ServiceNow column names
        assert "number" in df.columns
        assert "short_description" in df.columns
        assert "sys_created_on" in df.columns


class TestDetectFileType:
    """Auto-detection from realistic column sets."""

    def test_events_detected(self):
        df = _read_csv(FAKE_EVENTS_CSV.read_bytes())
        assert _detect_file_type(df) == "event_log"

    def test_tickets_detected(self):
        df = _read_csv(FAKE_TICKETS_CSV.read_bytes())
        assert _detect_file_type(df) == "ticket"


# ---------------------------------------------------------------------------
# Tests — event ingestion
# ---------------------------------------------------------------------------


class TestIngestEventsCsv:
    """Full event ingestion from the realistic CSV fixture."""

    def test_all_rows_ingested(self):
        async def _run():
            conn = await aiosqlite.connect(":memory:")
            conn.row_factory = aiosqlite.Row
            await conn.executescript(_SCHEMA_DDL)

            df = _read_csv(FAKE_EVENTS_CSV.read_bytes())
            count = await _ingest_event_logs(conn, df)

            # All 12 rows should ingest
            assert count == 12

            # --- devices created ---
            cursor = await conn.execute("SELECT COUNT(*) FROM devices")
            device_count = (await cursor.fetchone())[0]
            # Unique device_name+ip combos:
            #   3239_AP101_MERAKI/10.82.216.151
            #   0501-Lakewood-NJ-N3048P-40/10.142.72.40
            #   3862-Dover-NJ/10.131.208.2
            #   3778-Alton-IL-N1524P-X1-30/10.140.104.30
            #   5926-Southampton-NJ-N3248P-MDF-40/10.151.132.40
            #   LEB-FLEX-vWLC/10.254.71.4
            assert device_count == 6

            # --- event_ids preserved from the source CSV ---
            cursor = await conn.execute(
                "SELECT event_id FROM event_logs ORDER BY event_id"
            )
            ids = [row[0] for row in await cursor.fetchall()]
            assert ids[0] == 100000001
            assert ids[-1] == 100000012
            assert len(ids) == 12

            # --- [DEVICE_ID] prefix stripped from event_time ---
            cursor = await conn.execute(
                "SELECT event_time FROM event_logs WHERE event_id = 100000001"
            )
            row = await cursor.fetchone()
            assert row[0] == "20:00:04.470"
            assert "[DEVICE_ID]" not in row[0]

            # --- event_type_lookup populated ---
            cursor = await conn.execute("SELECT COUNT(*) FROM event_type_lookup")
            et_count = (await cursor.fetchone())[0]
            assert et_count >= 7  # 1,5,10,11,19,604,3805,5000,5001

            # --- severity classification for Node Down (5000) ---
            cursor = await conn.execute(
                "SELECT severity, category FROM event_type_lookup "
                "WHERE event_type_id = 5000"
            )
            row = await cursor.fetchone()
            assert row["severity"] == "P1"
            assert row["category"] == "connectivity"

            # --- severity classification for wireless (604) ---
            cursor = await conn.execute(
                "SELECT category FROM event_type_lookup WHERE event_type_id = 604"
            )
            row = await cursor.fetchone()
            assert row["category"] == "wireless"

            # --- site_code extracted from device_name ---
            cursor = await conn.execute(
                "SELECT site_code FROM devices WHERE device_name = '3239_AP101_MERAKI'"
            )
            row = await cursor.fetchone()
            assert row["site_code"] == "3239"

            # --- device with non-numeric prefix has no site_code ---
            cursor = await conn.execute(
                "SELECT site_code FROM devices WHERE device_name = 'LEB-FLEX-vWLC'"
            )
            row = await cursor.fetchone()
            assert row["site_code"] is None

            # --- duplicate device references don't create extra rows ---
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM devices WHERE device_name = '3239_AP101_MERAKI'"
            )
            assert (await cursor.fetchone())[0] == 1

            # --- NULL device row (EventType-3805, DeviceName=NULL) has no device link ---
            cursor = await conn.execute(
                "SELECT device_id FROM event_logs WHERE event_id = 100000004"
            )
            row = await cursor.fetchone()
            assert row["device_id"] is None

            await conn.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests — ticket ingestion
# ---------------------------------------------------------------------------


class TestIngestTicketsCsv:
    """Full ticket ingestion from the realistic CSV fixture."""

    def test_all_tickets_ingested(self):
        async def _run():
            conn = await aiosqlite.connect(":memory:")
            conn.row_factory = aiosqlite.Row
            await conn.executescript(_SCHEMA_DDL)

            df = _read_csv(FAKE_TICKETS_CSV.read_bytes())
            count = await _ingest_tickets(conn, df)
            assert count == 7

            # --- ticket types correctly detected ---
            cursor = await conn.execute(
                "SELECT ticket_number, ticket_type FROM sn_tickets ORDER BY ticket_number"
            )
            rows = await cursor.fetchall()
            types = {row["ticket_number"]: row["ticket_type"] for row in rows}
            assert types["CHG0083071"] == "CHG"
            assert types["INC0010001"] == "INC"
            assert types["RITM3427686"] == "RITM"

            # --- FEI site codes extracted from RITM (FEI1965, FEI1934, FEI1494) ---
            cursor = await conn.execute(
                "SELECT extracted_site_codes FROM sn_tickets "
                "WHERE ticket_number = 'RITM3427686'"
            )
            row = await cursor.fetchone()
            sites = json.loads(row["extracted_site_codes"])
            assert "1965" in sites
            assert "1934" in sites
            assert "1494" in sites

            # --- FEI with space (FEI 3239) also extracted ---
            cursor = await conn.execute(
                "SELECT extracted_site_codes FROM sn_tickets "
                "WHERE ticket_number = 'INC0010001'"
            )
            row = await cursor.fetchone()
            sites = json.loads(row["extracted_site_codes"])
            assert "3239" in sites

            # --- IPs extracted from descriptions ---
            cursor = await conn.execute(
                "SELECT extracted_ips FROM sn_tickets "
                "WHERE ticket_number = 'INC0010001'"
            )
            row = await cursor.fetchone()
            ips = json.loads(row["extracted_ips"])
            assert "10.82.216.151" in ips

            # --- sys_created_on mapped to created_on ---
            cursor = await conn.execute(
                "SELECT created_on FROM sn_tickets WHERE ticket_number = 'INC0010001'"
            )
            row = await cursor.fetchone()
            assert row["created_on"] == "01-15-2026 09:30"

            await conn.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests — end-to-end: events + tickets + cross-reference mapping
# ---------------------------------------------------------------------------


class TestEndToEndIngestWithMapping:
    """Events + tickets ingested together, then ticket↔device mapping runs."""

    def test_full_pipeline(self):
        async def _run():
            conn = await aiosqlite.connect(":memory:")
            conn.row_factory = aiosqlite.Row
            await conn.executescript(_SCHEMA_DDL)

            # 1) Ingest events first (creates devices)
            event_df = _read_csv(FAKE_EVENTS_CSV.read_bytes())
            event_count = await _ingest_event_logs(conn, event_df)
            assert event_count == 12

            # 2) Ingest tickets (extracts FEI codes, IPs, device names)
            ticket_df = _read_csv(FAKE_TICKETS_CSV.read_bytes())
            ticket_count = await _ingest_tickets(conn, ticket_df)
            assert ticket_count == 7

            # 3) Map ticket references to devices
            await _map_ticket_references(conn)

            # --- Verify device_ticket_map has entries ---
            cursor = await conn.execute("SELECT COUNT(*) FROM device_ticket_map")
            map_count = (await cursor.fetchone())[0]
            assert map_count > 0, "No device↔ticket mappings were created"

            # --- INC0010001 mentions 3239_AP101_MERAKI + 10.82.216.151 + FEI 3239 ---
            cursor = await conn.execute(
                """SELECT dtm.match_type, dtm.match_value
                   FROM device_ticket_map dtm
                   JOIN sn_tickets t ON dtm.ticket_id = t.ticket_id
                   JOIN devices d ON dtm.device_id = d.device_id
                   WHERE t.ticket_number = 'INC0010001'
                     AND d.device_name = '3239_AP101_MERAKI'
                   ORDER BY dtm.match_type"""
            )
            matches = await cursor.fetchall()
            match_types = [m["match_type"] for m in matches]
            assert "device_name" in match_types
            assert "ip_address" in match_types
            assert "site_code" in match_types

            # --- INC0010002 mentions 0501-Lakewood-NJ-N3048P-40 + 10.142.72.40 + FEI 501 ---
            cursor = await conn.execute(
                """SELECT DISTINCT dtm.match_type
                   FROM device_ticket_map dtm
                   JOIN sn_tickets t ON dtm.ticket_id = t.ticket_id
                   JOIN devices d ON dtm.device_id = d.device_id
                   WHERE t.ticket_number = 'INC0010002'
                     AND d.device_name = '0501-Lakewood-NJ-N3048P-40'
                   ORDER BY dtm.match_type"""
            )
            inc2_types = [m["match_type"] for m in await cursor.fetchall()]
            assert "device_name" in inc2_types
            assert "ip_address" in inc2_types
            assert "site_code" in inc2_types

            # --- CHG0083071 mentions 3862-Dover-NJ + 10.131.208.2 + FEI 3862 ---
            cursor = await conn.execute(
                """SELECT DISTINCT dtm.match_type
                   FROM device_ticket_map dtm
                   JOIN sn_tickets t ON dtm.ticket_id = t.ticket_id
                   JOIN devices d ON dtm.device_id = d.device_id
                   WHERE t.ticket_number = 'CHG0083071'
                     AND d.device_name = '3862-Dover-NJ'
                   ORDER BY dtm.match_type"""
            )
            chg_types = [m["match_type"] for m in await cursor.fetchall()]
            assert "device_name" in chg_types
            assert "site_code" in chg_types

            await conn.close()

        asyncio.run(_run())

    def test_idempotent_re_ingest(self):
        """Re-ingesting the same CSVs should not duplicate rows
        (ON CONFLICT upserts)."""

        async def _run():
            conn = await aiosqlite.connect(":memory:")
            conn.row_factory = aiosqlite.Row
            await conn.executescript(_SCHEMA_DDL)

            event_df = _read_csv(FAKE_EVENTS_CSV.read_bytes())
            ticket_df = _read_csv(FAKE_TICKETS_CSV.read_bytes())

            # First pass
            await _ingest_event_logs(conn, event_df)
            await _ingest_tickets(conn, ticket_df)

            # Second pass — same data
            await _ingest_event_logs(conn, event_df)
            await _ingest_tickets(conn, ticket_df)

            # event_logs uses ON CONFLICT(event_id) DO UPDATE
            cursor = await conn.execute("SELECT COUNT(*) FROM event_logs")
            assert (await cursor.fetchone())[0] == 12

            # sn_tickets uses ON CONFLICT(ticket_number) DO UPDATE
            cursor = await conn.execute("SELECT COUNT(*) FROM sn_tickets")
            assert (await cursor.fetchone())[0] == 7

            await conn.close()

        asyncio.run(_run())
