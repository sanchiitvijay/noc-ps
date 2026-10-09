"""
Sites router — GET /sites and GET /sites/{code}
"""

from __future__ import annotations

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database.connection import get_connection
from routers.dependencies import get_current_user
from services.sites_service import get_sites, get_site_details

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sites"], prefix="/sites")


@router.get(
    "",
    summary="Get paginated, filtered sites",
    responses={
        200: {"description": "Paginated list of sites with metrics"},
        401: {"description": "Authentication required"},
        500: {"description": "Internal server error"},
    },
)
async def list_sites(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: aiosqlite.Connection = Depends(get_connection),
    q: str = Query(default="", description="Text search by code, label or city"),
    state: str = Query(default="", description="Filter by geographic state"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page"),
) -> JSONResponse:
    try:
        result = await get_sites(conn, q=q, state=state, page=page, page_size=page_size)
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "OK",
                "data": result["data"],
                "meta": result["meta"],
                "states": result["states"]
            },
        )
    except Exception as exc:
        logger.error("list_sites error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve sites") from exc


@router.get(
    "/{code}",
    summary="Get site details",
    responses={
        200: {"description": "Site details with related metrics and events"},
        401: {"description": "Authentication required"},
        404: {"description": "Site not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_site(
    code: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    try:
        result = await get_site_details(conn, code)
        if not result:
            raise HTTPException(status_code=404, detail="Site not found")
            
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
        logger.error("get_site error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve site details") from exc
