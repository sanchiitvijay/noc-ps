"""
Ingest service — synchronous helpers for ingest job management.

The actual heavy lifting (CSV parsing + DB insertion) is done by
``workers/ingest_worker.py`` in a background asyncio task.
This service handles job record creation and status updates.
"""

from __future__ import annotations

import logging

import aiosqlite

from database.connection import execute_write, fetch_one
from utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def create_ingest_job(
    conn: aiosqlite.Connection,
    filename: str,
    triggered_by: int | None = None,
) -> dict:
    """Create a new ingest job record in the ``pending`` state.

    Args:
        conn: Active database connection.
        filename: Original filename of the uploaded file.
        triggered_by: User ID of the uploading user (nullable).

    Returns:
        The newly created ingest job row dict.
    """
    job_id = await execute_write(
        conn,
        """
        INSERT INTO ingest_jobs (filename, status, triggered_by)
        VALUES (?, 'pending', ?)
        """,
        (filename, triggered_by),
    )
    row = await fetch_one(conn, "SELECT * FROM ingest_jobs WHERE id = ?", (job_id,))
    if not row:
        raise RuntimeError("Failed to retrieve created ingest job")
    return row


async def get_ingest_job(
    conn: aiosqlite.Connection,
    job_id: int,
) -> dict:
    """Fetch an ingest job by primary key.

    Args:
        conn: Active database connection.
        job_id: Primary key of the ingest job.

    Returns:
        Ingest job row dict.

    Raises:
        NotFoundError: If the job does not exist.
    """
    row = await fetch_one(conn, "SELECT * FROM ingest_jobs WHERE id = ?", (job_id,))
    if not row:
        raise NotFoundError("IngestJob", str(job_id))
    return row


async def update_job_status(
    conn: aiosqlite.Connection,
    job_id: int,
    status: str,
    rows_processed: int = 0,
    error_message: str | None = None,
) -> None:
    """Update the status and progress of an ingest job.

    Args:
        conn: Active database connection.
        job_id: Primary key of the ingest job.
        status: New status string (running/completed/failed).
        rows_processed: Number of rows successfully processed so far.
        error_message: Error message if status is ``'failed'``.
    """
    if status == "running":
        await execute_write(
            conn,
            """
            UPDATE ingest_jobs
            SET status = 'running', started_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (job_id,),
        )
    elif status in ("completed", "failed"):
        await execute_write(
            conn,
            """
            UPDATE ingest_jobs
            SET status = ?,
                completed_at = CURRENT_TIMESTAMP,
                rows_processed = ?,
                error_message = ?
            WHERE id = ?
            """,
            (status, rows_processed, error_message, job_id),
        )
