"""
Solution summaries router — CRUD for /solution-summaries.

Provides endpoints to manage pre-computed ticket solution summaries stored in
the ``ticket_solution_summaries`` table. These summaries are checked FIRST
in the /error-info flow before any LLM call, enabling instant cached responses.

All routes require authentication (any role may read; admin/analyst may write).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database.connection import AsyncConnection, get_connection
from routers.dependencies import get_current_user, require_analyst_or_admin
from services.solution_summary_service import (
    delete_summary,
    get_summary,
    list_summaries,
    upsert_summary,
)
from utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/solution-summaries", tags=["Solution Summaries"])


# ---------------------------------------------------------------------------
# GET /solution-summaries — list all summaries
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="List saved solution summaries",
    responses={
        200: {"description": "List of saved solution summaries"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def list_solution_summaries(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: AsyncConnection = Depends(get_connection),
    device_id: int | None = Query(default=None, description="Filter by device ID"),
    event_type_id: int | None = Query(default=None, description="Filter by event type ID"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> JSONResponse:
    """Return a list of saved solution summaries.

    Summaries are pre-computed per device+event_type combination and are
    checked first in the /error-info flow before calling any external LLM.

    Args:
        current_user: Authenticated user (any role).
        conn: Injected database connection.
        device_id: Optional device filter.
        event_type_id: Optional event type filter.
        limit: Max rows to return.
        offset: Pagination offset.

    Returns:
        200 with list of summary objects.
    """
    try:
        summaries = await list_summaries(
            conn,
            device_id=device_id,
            event_type_id=event_type_id,
            limit=limit,
            offset=offset,
        )
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "OK", "data": summaries},
        )
    except Exception as exc:
        logger.error("Failed to list solution summaries: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve solution summaries") from exc


# ---------------------------------------------------------------------------
# GET /solution-summaries/{device_id}/{event_type_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{device_id}/{event_type_id}",
    summary="Get a saved solution summary for a device + event type",
    responses={
        200: {"description": "Solution summary found"},
        401: {"description": "Authentication required"},
        404: {"description": "No summary found for this device + event type"},
        500: {"description": "Internal server error"},
    },
)
async def get_solution_summary(
    device_id: int,
    event_type_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: AsyncConnection = Depends(get_connection),
) -> JSONResponse:
    """Return the saved solution summary for a specific device + event type pair.

    Args:
        device_id: Device primary key.
        event_type_id: Event type primary key.
        current_user: Authenticated user (any role).
        conn: Injected database connection.

    Returns:
        200 with summary object, or 404 if not found.
    """
    try:
        summary = await get_summary(conn, device_id, event_type_id)
        if not summary:
            raise NotFoundError(
                "SolutionSummary",
                f"device_id={device_id} event_type_id={event_type_id}",
            )
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "OK", "data": summary},
        )
    except NotFoundError:
        raise
    except Exception as exc:
        logger.error("Failed to fetch solution summary: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve solution summary") from exc


# ---------------------------------------------------------------------------
# POST /solution-summaries — create or update
# ---------------------------------------------------------------------------


@router.post(
    "",
    summary="Create or update a solution summary for a device + event type",
    responses={
        200: {"description": "Summary upserted successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Authentication required"},
        403: {"description": "Analyst or Admin role required"},
        500: {"description": "Internal server error"},
    },
)
async def create_or_update_solution_summary(
    body: dict,
    current_user: Annotated[dict, Depends(require_analyst_or_admin)],
    conn: AsyncConnection = Depends(get_connection),
) -> JSONResponse:
    """Insert or update a solution summary.

    Uses upsert semantics — if a summary already exists for the
    ``device_id`` + ``event_type_id`` pair, it will be overwritten.

    **Request body:**
    ```json
    {
        "device_id": 123,
        "event_type_id": 45,
        "hypothesis": "Root cause text...",
        "recommended_steps": ["Step 1", "Step 2"],
        "confidence": "high",
        "generated_by": "analyst",
        "source_tickets": ["INC001", "INC002"]
    }
    ```

    Args:
        body: JSON body with summary data.
        current_user: Authenticated analyst or admin.
        conn: Injected database connection.

    Returns:
        200 with the upserted summary data.

    Raises:
        400: If required fields are missing or invalid.
    """
    # Validate required fields
    device_id = body.get("device_id")
    event_type_id = body.get("event_type_id")
    hypothesis = body.get("hypothesis")
    recommended_steps = body.get("recommended_steps")

    missing = [
        f for f, v in [
            ("device_id", device_id),
            ("event_type_id", event_type_id),
            ("hypothesis", hypothesis),
            ("recommended_steps", recommended_steps),
        ] if v is None
    ]
    if missing:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"Missing required fields: {', '.join(missing)}",
                "data": None,
            },
        )

    if not isinstance(recommended_steps, list):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "recommended_steps must be a JSON array of strings",
                "data": None,
            },
        )

    confidence = body.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "confidence must be 'high', 'medium', or 'low'",
                "data": None,
            },
        )

    try:
        await upsert_summary(
            conn,
            device_id=int(device_id),
            event_type_id=int(event_type_id),
            hypothesis=str(hypothesis),
            recommended_steps=recommended_steps,
            confidence=confidence,
            generated_by=body.get("generated_by", "analyst"),
            source_tickets=body.get("source_tickets"),
        )
        saved = await get_summary(conn, int(device_id), int(event_type_id))
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Solution summary saved", "data": saved},
        )
    except Exception as exc:
        logger.error("Failed to upsert solution summary: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save solution summary") from exc


# ---------------------------------------------------------------------------
# DELETE /solution-summaries/{device_id}/{event_type_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{device_id}/{event_type_id}",
    summary="Delete a saved solution summary",
    responses={
        200: {"description": "Summary deleted"},
        401: {"description": "Authentication required"},
        403: {"description": "Analyst or Admin role required"},
        404: {"description": "No summary found to delete"},
        500: {"description": "Internal server error"},
    },
)
async def delete_solution_summary(
    device_id: int,
    event_type_id: int,
    current_user: Annotated[dict, Depends(require_analyst_or_admin)],
    conn: AsyncConnection = Depends(get_connection),
) -> JSONResponse:
    """Delete the saved solution summary for a device + event type.

    Args:
        device_id: Device primary key.
        event_type_id: Event type primary key.
        current_user: Authenticated analyst or admin.
        conn: Injected database connection.

    Returns:
        200 on success, 404 if no summary exists.
    """
    try:
        deleted = await delete_summary(conn, device_id, event_type_id)
        if not deleted:
            raise NotFoundError(
                "SolutionSummary",
                f"device_id={device_id} event_type_id={event_type_id}",
            )
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Solution summary deleted", "data": None},
        )
    except NotFoundError:
        raise
    except Exception as exc:
        logger.error("Failed to delete solution summary: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete solution summary") from exc
