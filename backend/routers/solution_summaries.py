"""
Solution summaries router — /solution-summaries.

Endpoints for manually reading, writing, and deleting cached LLM solution
summaries per event.
"""

from __future__ import annotations

import logging
from typing import Annotated

from aiosqlite import Connection as AsyncConnection
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database.connection import get_connection
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
# GET /solution-summaries
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="List saved solution summaries",
    responses={
        200: {"description": "List of summaries"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def list_solution_summaries(
    current_user: Annotated[dict, Depends(get_current_user)],
    event_id: int | None = Query(None, description="Filter by event"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    conn: AsyncConnection = Depends(get_connection),
) -> JSONResponse:
    try:
        summaries = await list_summaries(
            conn,
            event_id=event_id,
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
# GET /solution-summaries/{event_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{event_id}",
    summary="Get a saved solution summary for an event",
    responses={
        200: {"description": "Solution summary found"},
        401: {"description": "Authentication required"},
        404: {"description": "No summary found for this event"},
        500: {"description": "Internal server error"},
    },
)
async def get_solution_summary(
    event_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: AsyncConnection = Depends(get_connection),
) -> JSONResponse:
    try:
        summary = await get_summary(conn, event_id)
        if not summary:
            raise NotFoundError(
                "SolutionSummary",
                f"event_id={event_id}",
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
    summary="Create or update a solution summary for an event",
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
    event_id = body.get("event_id")
    hypothesis = body.get("hypothesis")
    recommended_steps = body.get("recommended_steps")

    missing = [
        f for f, v in [
            ("event_id", event_id),
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
            event_id=int(event_id),
            hypothesis=str(hypothesis),
            recommended_steps=recommended_steps,
            confidence=confidence,
            generated_by=body.get("generated_by", "analyst"),
            source_tickets=body.get("source_tickets"),
        )
        saved = await get_summary(conn, int(event_id))
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Solution summary saved", "data": saved},
        )
    except Exception as exc:
        logger.error("Failed to upsert solution summary: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save solution summary") from exc


# ---------------------------------------------------------------------------
# DELETE /solution-summaries/{event_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{event_id}",
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
    event_id: int,
    current_user: Annotated[dict, Depends(require_analyst_or_admin)],
    conn: AsyncConnection = Depends(get_connection),
) -> JSONResponse:
    try:
        deleted = await delete_summary(conn, event_id)
        if not deleted:
            raise NotFoundError(
                "SolutionSummary",
                f"event_id={event_id}",
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
