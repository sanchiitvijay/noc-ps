"""
Tickets router — GET /tickets and GET /tickets/{number}
"""

from __future__ import annotations

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database.connection import get_connection
from routers.dependencies import get_current_user
from services.tickets_service import get_tickets, get_ticket_details

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tickets"], prefix="/tickets")


@router.get(
    "",
    summary="Get paginated, filtered tickets",
    responses={
        200: {"description": "Paginated list of tickets"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def list_tickets(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: aiosqlite.Connection = Depends(get_connection),
    q: str = Query(default="", description="Text search by number or description"),
    kind: str = Query(default="", description="Filter by ticket type (e.g. INC, RITM)"),
    status: str = Query(default="", description="Filter by exact state"),
    linked: str = Query(default="", description="Filter by linked status (yes, no)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
) -> JSONResponse:
    try:
        result = await get_tickets(
            conn, q=q, kind=kind, status=status, linked=linked, page=page, page_size=page_size
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "OK",
                "data": result["data"],
                "meta": result["meta"],
                "kinds": result["kinds"],
                "statuses": result["statuses"]
            },
        )
    except Exception as exc:
        logger.error("list_tickets error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve tickets") from exc


@router.get(
    "/{number}",
    summary="Get ticket details",
    responses={
        200: {"description": "Ticket details with links"},
        401: {"description": "Authentication required"},
        404: {"description": "Ticket not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_ticket(
    number: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    try:
        result = await get_ticket_details(conn, number.upper())
        if not result:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "OK",
                "data": result
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_ticket error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve ticket details") from exc
