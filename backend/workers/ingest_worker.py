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
import logging
from typing import Any

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


def _detect_file_type(df: pd.DataFrame) -> str:
    """Determine whether *df* contains event log or ticket data.

    Normalizes column names to lowercase for comparison.

    Args:
        df: The parsed DataFrame.

    Returns:
        ``"event_log"`` or ``"ticket"`` or ``"unknown"``.
    """
    cols = {c.lower().strip() for c in df.columns}
    if EVENT_LOG_COLUMNS.issubset(cols):
        return "event_log"
    if TICKET_COLUMNS.issubset(cols):
        return "ticket"
    return "unknown"


def _safe_str(val: Any) -> str | None:
    """Convert a value to string, returning None for NaN/None.

    Args:
        val: Any pandas cell value.

    Returns:
        String or None.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return str(val).strip() or None


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
    # Normalize columns
    df.columns = [c.lower().strip() for c in df.columns]

    rows_processed = 0
    for _, row in df.iterrows():
        device_name = _safe_str(row.get("device_name"))
        event_type_name = _safe_str(row.get("event_type_name"))
        message = _safe_str(row.get("message"))
        event_time = _safe_str(row.get("event_time"))
        current_status = row.get("current_status")
        raw_detail = _safe_str(row.get("raw_detail"))

        if not device_name or not event_type_name:
            continue  # Skip incomplete rows

        # Resolve device_id
        async with conn.execute(
            "SELECT device_id FROM devices WHERE device_name = ? LIMIT 1",
            (device_name,),
        ) as cur:
            device_row = await cur.fetchone()
        device_id = device_row["device_id"] if device_row else None

        # Resolve event_type_id
        async with conn.execute(
            "SELECT event_type_id FROM event_type_lookup WHERE event_type_name = ? LIMIT 1",
            (event_type_name,),
        ) as cur:
            et_row = await cur.fetchone()
        event_type_id = et_row["event_type_id"] if et_row else None

        try:
            await conn.execute(
                """
                INSERT INTO event_logs
                    (event_time, event_type_id, event_type_name, message,
                     device_id, current_status, raw_detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_time,
                    event_type_id,
                    event_type_name,
                    message,
                    device_id,
                    int(current_status) if current_status is not None and not pd.isna(current_status) else None,
                    raw_detail,
                ),
            )
            rows_processed += 1
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

    df.columns = [c.lower().strip() for c in df.columns]
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
                    _to_json_str(row.get("extracted_site_codes")),
                    _to_json_str(row.get("extracted_ips")),
                    _to_json_str(row.get("extracted_device_names")),
                ),
            )
            rows_processed += 1
        except Exception as exc:
            logger.warning("Skipping ticket row '%s' due to error: %s", ticket_number, exc)

    await conn.commit()
    return rows_processed


# ---------------------------------------------------------------------------
# Main worker entry point
# ---------------------------------------------------------------------------

async def process_ingest_job(
    job_id: int,
    file_bytes: bytes,
    filename: str,
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
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
        elif lower_name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
        else:
            raise ValueError(f"Unsupported file extension: '{filename}'")

        # Replace empty strings with NaN for consistent handling
        df.replace("", None, inplace=True)

        file_type = _detect_file_type(df)
        logger.info("Job %d: detected file type = %s (%d rows)", job_id, file_type, len(df))

        async with get_db_context() as conn:
            conn.row_factory = aiosqlite.Row
            if file_type == "event_log":
                rows_processed = await _ingest_event_logs(conn, df)
            elif file_type == "ticket":
                rows_processed = await _ingest_tickets(conn, df)
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
