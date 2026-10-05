"""
Metrics router — GET /get-metrics.
"""

from __future__ import annotations

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from database.connection import get_connection
from routers.dependencies import get_current_user
from services.metrics_service import build_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Metrics"])


@router.get("/get-metrics", summary="Get aggregated NOC dashboard metrics")
async def get_metrics(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    """Return a comprehensive metrics payload for the NOC dashboard.

    Includes:
    - Total event counts (all time + approximate time windows)
    - Events grouped by severity and category
    - Top 10 alerting devices
    - 30-bucket event trend
    - ServiceNow ticket statistics
    - Total device count

    Note:
        ``event_logs.event_time`` contains time-only values (HH:MM:SS.mmm).
        Temporal window counts are approximated from event_id ranges.

    Args:
        current_user: Authenticated user (any role).
        conn: Injected database connection.

    Returns:
        200 response with full metrics dict.
    """
    data = await build_metrics(conn)
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "OK", "data": data},
    )
