"""
Background ingest worker — processes uploaded CSV/Excel files and inserts
rows into the appropriate database tables.

Detects file type by inspecting column names:
- Event data file (30_Days_*): columns include event_type_name, device_name → event_logs
- Ticket data file (SN_Tickets_*): columns include ticket_number, short_description → sn_tickets
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from typing import Any
import uuid

import aiosqlite
import pandas as pd

from config import settings
from database.connection import get_db_context
from services.ingest_service import update_job_status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column fingerprints for auto-detection
# ---------------------------------------------------------------------------

# Columns we expect to find in the event log CSV
EVENT_LOG_COLUMNS = {"event_type_name", "device_name", "message"}

# Columns we expect to find in the SN ticket CSV
TICKET_COLUMNS = {"ticket_number", "short_description", "state"}
SOURCE_EVENT_COLUMNS = {"eventid", "eventtime", "eventtype", "devicename", "message"}
SOURCE_TICKET_COLUMNS = {"number", "short_description", "state"}

EVENT_COLUMN_ALIASES = {
    "eventid": "event_id",
    "eventtime": "event_time",
    "eventtype": "event_type_id",
    "nodeid": "node_id",
    "devicename": "device_name",
    "ipaddress": "ip_address",
    "machinetype": "machine_type",
    "vendor": "vendor",
    "currentstatus": "current_status",
    "location": "location",
    "eventtypename": "event_type_name",
}

TICKET_COLUMN_ALIASES = {
    "number": "ticket_number",
    "sys_created_on": "created_on",
    "sys_updated_on": "updated_on",
}
EVENT_INGEST_COMMIT_INTERVAL = 500


def _detect_file_type(df: pd.DataFrame) -> str:
    """Determine whether *df* contains event log or ticket data.

    Normalizes column names to lowercase for comparison.

    Args:
        df: The parsed DataFrame.

    Returns:
        ``"event_log"`` or ``"ticket"`` or ``"unknown"``.
    """
    cols = {c.lower().strip() for c in df.columns}
    if EVENT_LOG_COLUMNS.issubset(cols) or SOURCE_EVENT_COLUMNS.issubset(cols):
        return "event_log"
    if TICKET_COLUMNS.issubset(cols) or SOURCE_TICKET_COLUMNS.issubset(cols):
        return "ticket"
    return "unknown"


def _normalize_columns(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    df.columns = [c.lower().strip() for c in df.columns]
    renames = {
        column: target
        for column, target in aliases.items()
        if column in df.columns and target not in df.columns
    }
    return df.rename(columns=renames)


def _read_csv(file_bytes: bytes) -> pd.DataFrame:
    """Read UTF-8 exports normally and fall back for Windows-1252 ServiceNow files."""
    try:
        return pd.read_csv(
            io.BytesIO(file_bytes),
            dtype=str,
            keep_default_na=False,
            encoding="utf-8-sig",
        )
    except UnicodeDecodeError:
        return pd.read_csv(
            io.BytesIO(file_bytes),
            dtype=str,
            keep_default_na=False,
            encoding="cp1252",
        )


def _safe_str(val: Any) -> str | None:
    """Convert a value to string, returning None for NaN/None.

    Args:
        val: Any pandas cell value.

    Returns:
        String or None.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    text = str(val).strip()
    return None if text.casefold() in {"", "null", "nan"} else text


def _safe_int(value: Any) -> int | None:
    raw = _safe_str(value)
    if raw is None:
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError, OverflowError):
        return None


async def _fetchone(conn, query: str, params: tuple = ()):
    cursor = await conn.execute(query, params)
    return await cursor.fetchone()


async def _fetchall(conn, query: str, params: tuple = ()):
    cursor = await conn.execute(query, params)
    return await cursor.fetchall()


async def _has_text_pk(conn, table: str, col: str) -> bool:
    try:
        cursor = await conn.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        for row in rows:
            name = row[1] if isinstance(row, (tuple, list)) else row["name"]
            ctype = row[2] if isinstance(row, (tuple, list)) else row["type"]
            if name == col:
                return "TEXT" in str(ctype).upper()
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Event log ingestion
# ---------------------------------------------------------------------------

async def _ingest_event_logs(conn: aiosqlite.Connection, df: pd.DataFrame) -> int:
    """Parse and upsert event log rows from a DataFrame.

    Normalizes column names to lowercase. Looks up ``device_id`` and
    ``event_type_id`` by name from the existing tables.

    Args:
        conn: Active database connection.
        df: DataFrame containing event log data.

    Returns:
        Number of rows successfully inserted/updated.
    """
    df = _normalize_columns(df, EVENT_COLUMN_ALIASES)
    is_text_device_id = await _has_text_pk(conn, "devices", "device_id")

    rows_processed = 0
    for _, row in df.iterrows():
        device_name = _safe_str(row.get("device_name"))
        event_type_name = _safe_str(row.get("event_type_name"))
        message = _safe_str(row.get("message"))
        event_time = _safe_str(row.get("event_time"))
        event_time = re.sub(r"^\[DEVICE_ID\]\s*", "", event_time).strip() if event_time else None
        event_id = _safe_int(row.get("event_id"))
        event_type_id = _safe_int(row.get("event_type_id"))
        current_status = _safe_int(row.get("current_status"))
        raw_detail = _safe_str(row.get("raw_detail"))

        device_id = None
        if device_name:
            ip_address = _safe_str(row.get("ip_address"))
            node_id = _safe_int(row.get("node_id"))
            site_match = re.match(r"^(\d{3,5})", device_name)
            site_code = site_match.group(1) if site_match else None
            site_name_match = re.match(
                r"^\d{3,5}[-_]([A-Za-z][\w-]*(?:-[A-Z]{2})?)(?:[-_]|$)",
                device_name,
            )
            site_name = site_name_match.group(1) if site_name_match else None

            # Resolve or create the device so imported source events remain queryable.
            device_row = await _fetchone(
                conn,
                "SELECT device_id FROM devices WHERE TRIM(device_name) = ? AND ip_address IS ? LIMIT 1",
                (device_name, ip_address),
            )
            if device_row:
                device_id = device_row["device_id"]
                await conn.execute(
                    """UPDATE devices SET node_id=COALESCE(?, node_id),
                       site_code=COALESCE(?, site_code), site_name=COALESCE(?, site_name),
                       machine_type=COALESCE(?, machine_type), vendor=COALESCE(?, vendor),
                       location=COALESCE(?, location) WHERE device_id=?""",
                    (
                        node_id, site_code, site_name,
                        _safe_str(row.get("machine_type")), _safe_str(row.get("vendor")),
                        _safe_str(row.get("location")), device_id,
                    ),
                )
            else:
                if is_text_device_id:
                    new_device_id = str(uuid.uuid4())
                    await conn.execute(
                        """INSERT INTO devices
                           (device_id, node_id, device_name, ip_address, site_code, site_name,
                            machine_type, vendor, location)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            new_device_id,
                            node_id, device_name, ip_address, site_code, site_name,
                            _safe_str(row.get("machine_type")), _safe_str(row.get("vendor")),
                            _safe_str(row.get("location")),
                        ),
                    )
                    device_id = new_device_id
                else:
                    cursor = await conn.execute(
                        """INSERT INTO devices
                           (node_id, device_name, ip_address, site_code, site_name,
                            machine_type, vendor, location)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            node_id, device_name, ip_address, site_code, site_name,
                            _safe_str(row.get("machine_type")), _safe_str(row.get("vendor")),
                            _safe_str(row.get("location")),
                        ),
                    )
                    device_id = cursor.lastrowid

        # Keep the event type ID/name pair consistent with the lookup table.
        if event_type_id is not None:
            et_row = await _fetchone(
                conn,
                "SELECT event_type_name FROM event_type_lookup WHERE event_type_id = ?",
                (event_type_id,),
            )
            if et_row:
                event_type_name = et_row["event_type_name"]
            else:
                event_type_name = event_type_name or f"EventType-{event_type_id}"
                lowered_name = event_type_name.lower()
                severity, category = "P4", "other"
                if "node down" in lowered_name or event_type_id in (5000, 5001):
                    severity, category = "P1", "connectivity"
                elif "node up" in lowered_name:
                    severity, category = "P3", "connectivity"
                elif "interface" in lowered_name:
                    severity, category = "P3" if "up" in lowered_name else "P2", "interface"
                elif event_type_id in (529, 3805):
                    category = "performance"
                elif event_type_id == 604:
                    category = "wireless"
                await conn.execute(
                    """INSERT INTO event_type_lookup
                       (event_type_id, event_type_name, severity, category)
                       VALUES (?, ?, ?, ?)""",
                    (event_type_id, event_type_name, severity, category),
                )
        elif event_type_name:
            et_row = await _fetchone(
                conn,
                "SELECT event_type_id FROM event_type_lookup WHERE event_type_name = ? LIMIT 1",
                (event_type_name,),
            )
            event_type_id = et_row["event_type_id"] if et_row else None

        if not event_type_name:
            continue

        try:
            if event_id is None:
                await conn.execute(
                    """INSERT INTO event_logs
                       (event_time, event_type_id, event_type_name, message,
                        device_id, current_status, raw_detail)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (event_time, event_type_id, event_type_name, message,
                     device_id, current_status, raw_detail),
                )
            else:
                await conn.execute(
                    """INSERT INTO event_logs
                       (event_id, event_time, event_type_id, event_type_name, message,
                        device_id, current_status, raw_detail)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(event_id) DO UPDATE SET
                           current_status = excluded.current_status""",
                    (event_id, event_time, event_type_id, event_type_name, message,
                     device_id, current_status, raw_detail),
                )
            rows_processed += 1
            if rows_processed % EVENT_INGEST_COMMIT_INTERVAL == 0:
                await conn.commit()
        except Exception as exc:
            logger.warning("Skipping event_log row due to error: %s", exc)

    await conn.commit()
    return rows_processed


# ---------------------------------------------------------------------------
# Ticket ingestion
# ---------------------------------------------------------------------------

async def _ingest_tickets(conn: aiosqlite.Connection, df: pd.DataFrame) -> int:
    """Parse and upsert ServiceNow ticket rows from a DataFrame.

    Uses INSERT OR REPLACE to handle duplicate ticket_number entries.

    Args:
        conn: Active database connection.
        df: DataFrame containing ticket data.

    Returns:
        Number of rows successfully inserted/updated.
    """
    import json as _json  # noqa: PLC0415

    df = _normalize_columns(df, TICKET_COLUMN_ALIASES)
    is_text_ticket_id = await _has_text_pk(conn, "sn_tickets", "ticket_id")
    known_devices = {
        row["device_name"].strip()
        for row in await _fetchall(conn, "SELECT device_name FROM devices WHERE device_name IS NOT NULL")
        if row["device_name"]
    }
    rows_processed = 0

    for _, row in df.iterrows():
        ticket_number = _safe_str(row.get("ticket_number"))
        if not ticket_number:
            continue

        # Determine ticket type from prefix
        ticket_type = None
        for prefix in ("INC", "RITM", "TASK", "CHG"):
            if ticket_number.upper().startswith(prefix):
                ticket_type = prefix
                break

        ticket_text = " ".join(
            _safe_str(row.get(column)) or ""
            for column in ("short_description", "description", "work_notes")
        )
        extracted_sites = sorted(set(re.findall(
            r"FEI[\s:|\-]*(\d{3,5})", ticket_text, re.IGNORECASE
        )))
        extracted_ips = sorted(set(re.findall(
            r"\b((?:\d{1,3}\.){3}\d{1,3})\b", ticket_text
        )))
        extracted_devices = sorted(
            device for device in known_devices
            if len(device) > 5 and device in ticket_text
        )

        # Handle extracted JSON arrays — accept both list and string
        def _to_json_str(val: Any) -> str | None:
            raw = _safe_str(val)
            if raw is None:
                return None
            try:
                # If already a JSON string, validate and return it
                parsed = _json.loads(raw)
                return _json.dumps(parsed)
            except Exception:
                # Treat as a plain value, wrap in list
                return _json.dumps([raw])

        try:
            if is_text_ticket_id:
                new_ticket_id = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO sn_tickets
                        (ticket_id, ticket_number, ticket_type, state, created_on, updated_on,
                         closed_at, assignment_group, short_description, description,
                         work_notes, extracted_site_codes, extracted_ips, extracted_device_names)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticket_number) DO UPDATE SET
                        state               = excluded.state,
                        updated_on          = excluded.updated_on,
                        closed_at           = excluded.closed_at,
                        work_notes          = excluded.work_notes,
                        extracted_site_codes = excluded.extracted_site_codes,
                        extracted_ips        = excluded.extracted_ips,
                        extracted_device_names = excluded.extracted_device_names
                    """,
                    (
                        new_ticket_id,
                        ticket_number,
                        ticket_type,
                        _safe_str(row.get("state")),
                        _safe_str(row.get("created_on") or row.get("opened_at")),
                        _safe_str(row.get("updated_on") or row.get("sys_updated_on")),
                        _safe_str(row.get("closed_at")),
                        _safe_str(row.get("assignment_group")),
                        _safe_str(row.get("short_description")),
                        _safe_str(row.get("description")),
                        _safe_str(row.get("work_notes")),
                        _to_json_str(row.get("extracted_site_codes")) or (_json.dumps(extracted_sites) if extracted_sites else None),
                        _to_json_str(row.get("extracted_ips")) or (_json.dumps(extracted_ips) if extracted_ips else None),
                        _to_json_str(row.get("extracted_device_names")) or (_json.dumps(extracted_devices) if extracted_devices else None),
                    ),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO sn_tickets
                        (ticket_number, ticket_type, state, created_on, updated_on,
                         closed_at, assignment_group, short_description, description,
                         work_notes, extracted_site_codes, extracted_ips, extracted_device_names)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticket_number) DO UPDATE SET
                        state               = excluded.state,
                        updated_on          = excluded.updated_on,
                        closed_at           = excluded.closed_at,
                        work_notes          = excluded.work_notes,
                        extracted_site_codes = excluded.extracted_site_codes,
                        extracted_ips        = excluded.extracted_ips,
                        extracted_device_names = excluded.extracted_device_names
                    """,
                    (
                        ticket_number,
                        ticket_type,
                        _safe_str(row.get("state")),
                        _safe_str(row.get("created_on") or row.get("opened_at")),
                        _safe_str(row.get("updated_on") or row.get("sys_updated_on")),
                        _safe_str(row.get("closed_at")),
                        _safe_str(row.get("assignment_group")),
                        _safe_str(row.get("short_description")),
                        _safe_str(row.get("description")),
                        _safe_str(row.get("work_notes")),
                        _to_json_str(row.get("extracted_site_codes")) or (_json.dumps(extracted_sites) if extracted_sites else None),
                        _to_json_str(row.get("extracted_ips")) or (_json.dumps(extracted_ips) if extracted_ips else None),
                        _to_json_str(row.get("extracted_device_names")) or (_json.dumps(extracted_devices) if extracted_devices else None),
                    ),
                )
            rows_processed += 1
        except Exception as exc:
            logger.warning("Skipping ticket row '%s' due to error: %s", ticket_number, exc)

    await conn.commit()
    return rows_processed


async def _map_ticket_references(conn: aiosqlite.Connection) -> None:
    """Create exact site, device-name, and IP links for imported tickets."""
    is_text_dtmap_id = await _has_text_pk(conn, "device_ticket_map", "id")

    # If any tickets have NULL ticket_id in text PK mode, populate them
    if await _has_text_pk(conn, "sn_tickets", "ticket_id"):
        null_tkts = await _fetchall(conn, "SELECT ticket_number FROM sn_tickets WHERE ticket_id IS NULL")
        for nt in null_tkts:
            tnum = nt[0] if isinstance(nt, (tuple, list)) else nt["ticket_number"]
            await conn.execute("UPDATE sn_tickets SET ticket_id = ? WHERE ticket_number = ?", (str(uuid.uuid4()), tnum))
        if null_tkts:
            await conn.commit()

    devices = await _fetchall(
        conn,
        "SELECT device_id, device_name, site_code, ip_address FROM devices WHERE device_id IS NOT NULL"
    )
    tickets = await _fetchall(
        conn,
        """SELECT ticket_id, extracted_site_codes, extracted_device_names, extracted_ips
           FROM sn_tickets WHERE ticket_id IS NOT NULL"""
    )

    for ticket in tickets:
        try:
            sites = set(json.loads(ticket["extracted_site_codes"] or "[]"))
            names = set(json.loads(ticket["extracted_device_names"] or "[]"))
            ips = set(json.loads(ticket["extracted_ips"] or "[]"))
        except (json.JSONDecodeError, TypeError):
            continue
        normalized_sites = {str(site).lstrip("0") or "0" for site in sites}
        for device in devices:
            matches = []
            if device["site_code"] and (str(device["site_code"]).lstrip("0") or "0") in normalized_sites:
                matches.append(("site_code", device["site_code"], 0.9))
            normalized_device_name = device["device_name"].strip()
            if normalized_device_name in names:
                matches.append(("device_name", device["device_name"], 0.8))
            if device["ip_address"] in ips:
                matches.append(("ip_address", device["ip_address"], 0.7))
            for match_type, match_value, confidence in matches:
                if is_text_dtmap_id:
                    await conn.execute(
                        """INSERT OR IGNORE INTO device_ticket_map
                           (id, device_id, ticket_id, match_type, match_value, confidence)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (str(uuid.uuid4()), device["device_id"], ticket["ticket_id"], match_type, match_value, confidence),
                    )
                else:
                    await conn.execute(
                        """INSERT OR IGNORE INTO device_ticket_map
                           (device_id, ticket_id, match_type, match_value, confidence)
                           VALUES (?, ?, ?, ?, ?)""",
                        (device["device_id"], ticket["ticket_id"], match_type, match_value, confidence),
                    )
    await conn.commit()


# ---------------------------------------------------------------------------
# Main worker entry point
# ---------------------------------------------------------------------------

async def process_ingest_job(
    job_id: int,
    file_bytes: bytes,
    filename: str,
    file_type: str = "auto",
) -> None:
    """Main background task — parse the uploaded file and ingest into the DB.

    Detects file type automatically from column names. Updates the
    ``ingest_jobs`` table with status, progress, and any error message.

    This function is designed to run in a ``asyncio.create_task`` background
    coroutine and should NOT raise exceptions (errors are recorded in the DB).

    Args:
        job_id: Primary key of the ingest_jobs row to update.
        file_bytes: Raw bytes of the uploaded file.
        filename: Original filename (used for extension detection).
    """
    async with get_db_context() as conn:
        conn.row_factory = aiosqlite.Row
        await update_job_status(conn, job_id, "running")

    try:
        # Parse file into DataFrame
        lower_name = filename.lower()
        if lower_name.endswith(".csv"):
            df = _read_csv(file_bytes)
        elif lower_name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
        else:
            raise ValueError(f"Unsupported file extension: '{filename}'")

        # Replace empty strings with NaN for consistent handling
        df.replace("", None, inplace=True)

        if file_type == "auto":
            file_type = _detect_file_type(df)
            
        logger.info("Job %d: processing as file type = %s (%d rows)", job_id, file_type, len(df))

        async with get_db_context() as conn:
            conn.row_factory = aiosqlite.Row
            if file_type == "event_log":
                rows_processed = await _ingest_event_logs(conn, df)
            elif file_type == "ticket":
                rows_processed = await _ingest_tickets(conn, df)
                await _map_ticket_references(conn)
            else:
                raise ValueError(
                    "Could not identify file type from columns. "
                    f"Found: {list(df.columns)[:10]}"
                )

        async with get_db_context() as conn:
            conn.row_factory = aiosqlite.Row
            await update_job_status(conn, job_id, "completed", rows_processed=rows_processed)

        logger.info("Job %d completed: %d rows processed", job_id, rows_processed)

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Job %d FAILED: %s", job_id, error_msg, exc_info=True)
        async with get_db_context() as conn:
            conn.row_factory = aiosqlite.Row
            await update_job_status(conn, job_id, "failed", error_message=error_msg)
