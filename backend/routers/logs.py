"""
Logs router — GET /get-logs (event logs, paginated + filtered).
"""

from __future__ import annotations

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database.connection import get_connection
from routers.dependencies import get_current_user
from services.logs_service import get_event_logs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Logs"])


@router.get(
    "/get-logs",
    summary="Get paginated, filtered event logs",
    responses={
        200: {
            "description": (
                "Paginated list of event logs enriched with device and event type metadata."
            )
        },
        401: {"description": "Authentication required"},
        422: {"description": "Invalid query parameters"},
        500: {"description": "Internal server error"},
    },
)
async def get_logs(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: aiosqlite.Connection = Depends(get_connection),
    event_id: int | None = Query(default=None, description="Filter by event ID"),
    device_id: int | None = Query(default=None, description="Filter by device ID"),
    event_type_id: int | None = Query(default=None, description="Filter by event type ID"),
    severity: str | None = Query(
        default=None,
        description="Filter by severity: P1 | P2 | P3 | P4",
    ),
    search: str | None = Query(
        default=None,
        description="Text search in message and raw_detail fields",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Results per page (max 200)",
    ),
) -> JSONResponse:
    """Return a paginated list of event_logs enriched with device and event type metadata.

    Supports filtering by event_id, device, event type, severity, and free-text search.
    Results are ordered by event_id DESC (newest first).

    Args:
        current_user: Authenticated user (any role).
        conn: Injected database connection.
        event_id: Optional event ID filter.
        device_id: Optional device filter.
        event_type_id: Optional event type filter.
        severity: Optional severity level filter.
        search: Optional text to search in message/raw_detail.
        page: Page number.
        page_size: Items per page.

    Returns:
        200 response with data array and pagination meta.

    Raises:
        500: On unexpected database errors.
    """
    try:
        result = await get_event_logs(
            conn,
            event_id=event_id,
            device_id=device_id,
            event_type_id=event_type_id,
            severity=severity,
            search=search,
            page=page,
            page_size=page_size,
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "OK",
                "data": result["data"],
                "meta": result["meta"],
            },
        )
    except Exception as exc:
        logger.error("get_logs error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve event logs") from exc
