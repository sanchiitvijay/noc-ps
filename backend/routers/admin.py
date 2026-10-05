"""
Admin router — /admin/activity-log and /admin/ingest-excel.

All routes in this router require the ``admin`` role.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.responses import JSONResponse

from config import settings
from database.connection import get_connection
from routers.dependencies import get_current_user, require_admin
from schemas.logs import ActivityLogCreate
from services.ingest_service import create_ingest_job, get_ingest_job
from services.logs_service import create_activity_log, get_activity_logs
from utils.exceptions import FileTooLargeError
from workers.ingest_worker import process_ingest_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Activity log endpoints
# ---------------------------------------------------------------------------


@router.get("/activity-log", summary="List activity logs (admin only)")
async def list_activity_logs(
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> JSONResponse:
    """Return a paginated list of all activity log entries.

    Joins the ``users`` table to include the username alongside user_id.

    Args:
        current_user: Authenticated admin user.
        conn: Injected database connection.
        page: Page number (1-indexed).
        page_size: Items per page.

    Returns:
        200 response with activity log data and pagination meta.
    """
    result = await get_activity_logs(conn, page=page, page_size=page_size)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "OK",
            "data": result["data"],
            "meta": result["meta"],
        },
    )


@router.post(
    "/activity-log",
    status_code=status.HTTP_201_CREATED,
    summary="Manually create an activity log entry (admin only)",
)
async def create_manual_activity_log(
    body: ActivityLogCreate,
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    """Manually insert an activity log entry.

    Useful for recording external events or test entries.

    Args:
        body: ActivityLogCreate with action, endpoint, and optional fields.
        current_user: Authenticated admin user (becomes the log's user_id).
        conn: Injected database connection.

    Returns:
        201 response with the created entry's ID.
    """
    log_id = await create_activity_log(
        conn,
        user_id=current_user["id"],
        action=body.action,
        endpoint=body.endpoint,
        ip_address=body.ip_address,
        request_body=body.request_body,
        response_status=body.response_status,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "success": True,
            "message": "Activity log entry created",
            "data": {"id": log_id},
        },
    )


# ---------------------------------------------------------------------------
# Ingest endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/ingest-excel",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a CSV/Excel file for background ingestion (admin only)",
)
async def ingest_excel(
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
    file: UploadFile = ...,
) -> JSONResponse:
    """Accept a CSV or Excel file upload and queue it for background processing.

    The file is validated for size and extension, then a job record is created
    in the ``ingest_jobs`` table. The actual processing runs in a background
    asyncio task — the response returns immediately with a ``job_id``.

    Poll ``GET /admin/ingest-excel/{job_id}`` to check progress.

    Args:
        current_user: Authenticated admin user.
        conn: Injected database connection.
        file: Multipart-uploaded file (CSV or Excel).

    Returns:
        202 response with the job_id and initial job state.

    Raises:
        400: If the file extension is not supported.
        413: If the file exceeds MAX_INGEST_FILE_SIZE_MB.
    """
    # Validate file extension
    allowed_extensions = {".csv", ".xlsx", ".xls"}
    filename = file.filename or "upload"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "message": f"Unsupported file type '{ext}'. Allowed: {allowed_extensions}",
                "data": None,
            },
        )

    # Read file and check size
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_ingest_bytes:
        raise FileTooLargeError(settings.MAX_INGEST_FILE_SIZE_MB)

    # Create pending job record
    job = await create_ingest_job(conn, filename=filename, triggered_by=current_user["id"])
    job_id = job["id"]

    # Launch background task — don't await it
    asyncio.create_task(
        process_ingest_job(
            job_id=job_id,
            file_bytes=file_bytes,
            filename=filename,
        )
    )

    logger.info(
        "Ingest job %d queued for file '%s' by user %d",
        job_id, filename, current_user["id"]
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "success": True,
            "message": f"File accepted. Job {job_id} is queued for processing.",
            "data": {
                "id": job["id"],
                "filename": job["filename"],
                "status": job["status"],
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "rows_processed": job.get("rows_processed", 0),
                "error_message": job.get("error_message"),
                "triggered_by": job.get("triggered_by"),
            },
        },
    )


@router.get(
    "/ingest-excel/{job_id}",
    summary="Get the status of an ingest job (admin only)",
)
async def get_ingest_status(
    job_id: int,
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    """Poll the status of a previously submitted ingest job.

    Args:
        job_id: Primary key of the ingest job.
        current_user: Authenticated admin user.
        conn: Injected database connection.

    Returns:
        200 response with current job state and progress.

    Raises:
        404: If the job_id does not exist.
    """
    job = await get_ingest_job(conn, job_id)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "OK",
            "data": {
                "id": job["id"],
                "filename": job["filename"],
                "status": job["status"],
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "rows_processed": job.get("rows_processed", 0),
                "error_message": job.get("error_message"),
                "triggered_by": job.get("triggered_by"),
            },
        },
    )
