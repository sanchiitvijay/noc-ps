"""
Admin router — /admin/activity-log, /admin/ingest-error-csv, and /admin/ingest-ticket-csv.

All routes in this router require the ``admin`` role.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Query, UploadFile, status, Form
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

async def _handle_ingest(
    file: UploadFile,
    current_user: dict,
    conn: aiosqlite.Connection,
    file_type: str,
) -> JSONResponse:
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

    file_bytes = await file.read()
    if len(file_bytes) > settings.max_ingest_bytes:
        raise FileTooLargeError(settings.MAX_INGEST_FILE_SIZE_MB)

    job = await create_ingest_job(conn, filename=filename, triggered_by=current_user["id"])
    job_id = job["id"]

    asyncio.create_task(
        process_ingest_job(
            job_id=job_id,
            file_bytes=file_bytes,
            filename=filename,
            file_type=file_type,
        )
    )

    logger.info(
        "Ingest job %d queued for file '%s' (type %s) by user %d",
        job_id, filename, file_type, current_user["id"]
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

@router.post(
    "/ingest/error-csv",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload an error CSV file for background ingestion (admin only)",
)
async def ingest_error_csv(
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
    file: UploadFile = ...,
) -> JSONResponse:
    return await _handle_ingest(file, current_user, conn, "event_log")


@router.post(
    "/ingest/ticket-csv",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a ticket CSV file for background ingestion (admin only)",
)
async def ingest_ticket_csv(
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
    file: UploadFile = ...,
) -> JSONResponse:
    return await _handle_ingest(file, current_user, conn, "ticket")


@router.post(
    "/ingest-excel",
    status_code=status.HTTP_202_ACCEPTED,
    summary=(
        "Upload a CSV (or Excel) for background ingestion — auto-detects event or ticket data (admin only). "
        "This is the primary endpoint called by the frontend."
    ),
)
async def ingest_excel(
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
    file: UploadFile = ...,
) -> JSONResponse:
    """Auto-detect whether the uploaded file is an event log or ticket CSV
    and dispatch to the appropriate handler.

    The file type is determined by column names inside the file, so the caller
    does not need to choose between /ingest/error-csv and /ingest/ticket-csv.
    """
    return await _handle_ingest(file, current_user, conn, "auto")


@router.get(
    "/ingest-excel/{job_id}",
    summary="Get the status of an ingest job (admin only)",
)
async def get_ingest_status(
    job_id: int,
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    job = await get_ingest_job(conn, job_id)
    import json
    
    def parse_json(val):
        if not val:
            return None
        try:
            return json.loads(val)
        except Exception:
            return val

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
                "dataset": job.get("dataset"),
                "size_bytes": job.get("size_bytes"),
                "progress": job.get("progress", 0),
                "stage": job.get("stage"),
                "preview": parse_json(job.get("preview")),
                "mapping": parse_json(job.get("mapping")),
                "options": parse_json(job.get("options")),
                "stats": parse_json(job.get("stats"))
            },
        },
    )


@router.get(
    "/ingest-jobs",
    summary="List all ingest jobs (admin only)",
)
async def list_ingest_jobs(
    current_user: Annotated[dict, Depends(require_admin)],
    conn: aiosqlite.Connection = Depends(get_connection),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> JSONResponse:
    from database.connection import fetch_all
    from utils.pagination import get_offset, paginate
    import json
    
    def parse_json(val):
        if not val:
            return None
        try:
            return json.loads(val)
        except Exception:
            return val
            
    count_row = await conn.execute("SELECT COUNT(*) AS cnt FROM ingest_jobs")
    count_dict = dict(await count_row.fetchone() or {})
    total = count_dict.get("cnt", 0)
    
    if total == 0:
         return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "OK",
                "data": [],
                "meta": paginate(0, page, page_size)
            }
         )
         
    offset = get_offset(page, page_size)
    cursor = await conn.execute(
        "SELECT * FROM ingest_jobs ORDER BY id DESC LIMIT ? OFFSET ?",
        (page_size, offset)
    )
    rows = await cursor.fetchall()
    
    data = []
    for r in rows:
        job = dict(r)
        data.append({
            "id": job["id"],
            "filename": job["filename"],
            "status": job["status"],
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "rows_processed": job.get("rows_processed", 0),
            "error_message": job.get("error_message"),
            "triggered_by": job.get("triggered_by"),
            "dataset": job.get("dataset"),
            "size_bytes": job.get("size_bytes"),
            "progress": job.get("progress", 0),
            "stage": job.get("stage"),
            "preview": parse_json(job.get("preview")),
            "mapping": parse_json(job.get("mapping")),
            "options": parse_json(job.get("options")),
            "stats": parse_json(job.get("stats"))
        })
        
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": "OK",
            "data": data,
            "meta": paginate(total, page, page_size)
        }
    )
