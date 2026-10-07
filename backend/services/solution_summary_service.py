"""
Solution summary service — CRUD for the ticket_solution_summaries table.

This table caches pre-computed LLM solution summaries per device+event_type.
The /error-info flow checks this table FIRST before calling any LLM, so
repeated queries for the same device+event_type return instantly and save
API tokens.

CRUD endpoints are exposed under /solution-summaries (auth required).
"""

from __future__ import annotations

import json
import logging

from database.connection import execute_write, fetch_all, fetch_one

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def get_summary(
    conn,
    device_id: int,
    event_type_id: int,
) -> dict | None:
    """Fetch the saved solution summary for a device + event type pair.

    Args:
        conn: Active database connection.
        device_id: Device primary key.
        event_type_id: Event type primary key.

    Returns:
        Summary dict (with ``recommended_steps`` as a Python list) or ``None``.
    """
    row = await fetch_one(
        conn,
        """
        SELECT * FROM ticket_solution_summaries
        WHERE device_id = ? AND event_type_id = ?
        """,
        (device_id, event_type_id),
    )
    if not row:
        return None
    return _deserialize(row)


async def list_summaries(
    conn,
    device_id: int | None = None,
    event_type_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List saved solution summaries with optional filters.

    Args:
        conn: Active database connection.
        device_id: Optional filter by device.
        event_type_id: Optional filter by event type.
        limit: Max rows.
        offset: Pagination offset.

    Returns:
        List of summary dicts.
    """
    conditions: list[str] = []
    params: list = []
    if device_id is not None:
        conditions.append("device_id = ?")
        params.append(device_id)
    if event_type_id is not None:
        conditions.append("event_type_id = ?")
        params.append(event_type_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])

    rows = await fetch_all(
        conn,
        f"""
        SELECT * FROM ticket_solution_summaries
        {where}
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params),
    )
    return [_deserialize(r) for r in rows]


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


async def upsert_summary(
    conn,
    device_id: int,
    event_type_id: int,
    hypothesis: str,
    recommended_steps: list[str],
    confidence: str = "medium",
    generated_by: str = "rule-based",
    source_tickets: list[str] | None = None,
) -> int:
    """Insert or replace a solution summary for a device+event_type pair.

    Uses SQLite's ``INSERT OR REPLACE`` so callers don't need to check
    existence first.

    Args:
        conn: Active database connection.
        device_id: Device primary key.
        event_type_id: Event type primary key.
        hypothesis: Root cause hypothesis text.
        recommended_steps: Ordered list of remediation steps.
        confidence: ``"high"``, ``"medium"``, or ``"low"``.
        generated_by: Source tag (``"gemini"``, ``"groq"``, ``"rule-based"``, etc.).
        source_tickets: Optional list of ticket numbers that informed this summary.

    Returns:
        The row id of the upserted record.
    """
    steps_json   = json.dumps(recommended_steps)
    tickets_json = json.dumps(source_tickets or [])

    return await execute_write(
        conn,
        """
        INSERT INTO ticket_solution_summaries
            (device_id, event_type_id, hypothesis, recommended_steps,
             confidence, generated_by, source_tickets, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(device_id, event_type_id) DO UPDATE SET
            hypothesis        = excluded.hypothesis,
            recommended_steps = excluded.recommended_steps,
            confidence        = excluded.confidence,
            generated_by      = excluded.generated_by,
            source_tickets    = excluded.source_tickets,
            updated_at        = CURRENT_TIMESTAMP
        """,
        (device_id, event_type_id, hypothesis, steps_json,
         confidence, generated_by, tickets_json),
    )


async def delete_summary(conn, device_id: int, event_type_id: int) -> bool:
    """Delete the solution summary for a device+event_type pair.

    Args:
        conn: Active database connection.
        device_id: Device primary key.
        event_type_id: Event type primary key.

    Returns:
        ``True`` if a row was deleted, ``False`` if not found.
    """
    # Check existence first to return meaningful bool
    existing = await get_summary(conn, device_id, event_type_id)
    if not existing:
        return False
    await execute_write(
        conn,
        "DELETE FROM ticket_solution_summaries WHERE device_id = ? AND event_type_id = ?",
        (device_id, event_type_id),
    )
    return True


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _deserialize(row: dict) -> dict:
    """Convert JSON-serialised fields back to Python objects.

    Args:
        row: Raw DB row dict.

    Returns:
        Row with ``recommended_steps`` and ``source_tickets`` as lists.
    """
    result = dict(row)
    try:
        result["recommended_steps"] = json.loads(result.get("recommended_steps") or "[]")
    except (json.JSONDecodeError, TypeError):
        result["recommended_steps"] = []
    try:
        result["source_tickets"] = json.loads(result.get("source_tickets") or "[]")
    except (json.JSONDecodeError, TypeError):
        result["source_tickets"] = []
    return result
