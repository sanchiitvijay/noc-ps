"""
Solution summary service — CRUD for the ticket_solution_summaries table.

This table caches pre-computed LLM solution summaries per event_id.
The /error-info flow checks this table FIRST before calling any LLM, so
repeated queries for the same event_id return instantly and save
API tokens.

CRUD endpoints are exposed under /solution-summaries (auth required).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from config import settings
from database.connection import execute_write, fetch_all, fetch_one

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def get_summary(
    conn,
    event_id: int,
) -> dict | None:
    """Fetch the saved solution summary for an event.
    Only returns the summary if it is within the configured cache TTL.

    Args:
        conn: Active database connection.
        event_id: Event primary key.

    Returns:
        Summary dict (with ``recommended_steps`` as a Python list) or ``None``.
    """
    row = await fetch_one(
        conn,
        """
        SELECT * FROM ticket_solution_summaries
        WHERE event_id = ? AND updated_at >= datetime('now', ?)
        """,
        (event_id, f"-{settings.SOLUTION_SUMMARY_CACHE_TTL_MINUTES} minutes"),
    )
    if not row:
        return None
    return _deserialize(row)


async def list_summaries(
    conn,
    event_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List saved solution summaries with optional filters.

    Args:
        conn: Active database connection.
        event_id: Optional filter by event.
        limit: Max rows.
        offset: Pagination offset.

    Returns:
        List of summary dicts.
    """
    conditions: list[str] = []
    params: list = []
    if event_id is not None:
        conditions.append("event_id = ?")
        params.append(event_id)

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
    event_id: int,
    hypothesis: str,
    recommended_steps: list[str],
    confidence: str = "medium",
    generated_by: str = "rule-based",
    source_tickets: list[str] | None = None,
) -> int:
    """Insert or replace a solution summary for an event.

    Uses SQLite's ``INSERT OR REPLACE`` so callers don't need to check
    existence first.

    Args:
        conn: Active database connection.
        event_id: Event primary key.
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
            (event_id, hypothesis, recommended_steps,
             confidence, generated_by, source_tickets, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(event_id) DO UPDATE SET
            hypothesis        = excluded.hypothesis,
            recommended_steps = excluded.recommended_steps,
            confidence        = excluded.confidence,
            generated_by      = excluded.generated_by,
            source_tickets    = excluded.source_tickets,
            updated_at        = CURRENT_TIMESTAMP
        """,
        (event_id, hypothesis, steps_json,
         confidence, generated_by, tickets_json),
    )


async def delete_summary(conn, event_id: int) -> bool:
    """Delete the solution summary for an event.

    Args:
        conn: Active database connection.
        event_id: Event primary key.

    Returns:
        ``True`` if a row was deleted, ``False`` if not found.
    """
    # Query directly (no freshness filter) so stale summaries can be deleted too.
    row = await fetch_one(
        conn,
        "SELECT event_id FROM ticket_solution_summaries WHERE event_id = ?",
        (event_id,),
    )
    if not row:
        return False
    await execute_write(
        conn,
        "DELETE FROM ticket_solution_summaries WHERE event_id = ?",
        (event_id,),
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
