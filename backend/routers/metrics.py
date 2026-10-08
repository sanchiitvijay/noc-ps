"""
Metrics router — GET /get-metrics.
"""

from __future__ import annotations

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database.connection import get_connection
from routers.dependencies import get_current_user
from services.metrics_service import build_metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Metrics"])


@router.get(
    "/get-metrics",
    summary="Get aggregated NOC dashboard metrics",
    responses={
        200: {
            "description": (
                "Comprehensive metrics payload including event counts, severity breakdown, "
                "top devices, and event trend."
            )
        },
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def get_metrics(
    current_user: Annotated[dict, Depends(get_current_user)],
    time_window: str = Query("all", description="Time window: 24h, 7d, 30d, all"),
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    try:
        data = await build_metrics(conn, time_window)
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "OK", "data": data},
        )
    except Exception as exc:
        logger.error("get_metrics error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics") from exc
