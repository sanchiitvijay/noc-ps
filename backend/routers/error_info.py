"""
Error info router — GET /error-info.

Returns a full analysis panel for a given device + event type combination,
including full ticket + event data, raw error logs, live diagnostics,
and an LLM-generated remediation suggestion.

When no historical tickets exist for the device, the LLM still produces
an analysis and ``suggested_solution.generated_by`` is set to
``"no_ticket_llm"`` so the frontend can display "LLM gave this response".
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from database.connection import AsyncConnection, get_connection
from routers.dependencies import get_current_user
from services.error_info_service import build_error_info

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Error Info"])


@router.get("/error-info", summary="Get full error analysis panel for a device + event type")
async def get_error_info(
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: AsyncConnection = Depends(get_connection),
    device_id: int | None = Query(
        default=None,
        description="Device primary key (preferred over device_name)",
    ),
    device_name: str | None = Query(
        default=None,
        description="Device name (partial match). Used if device_id not provided.",
    ),
    event_type_id: int | None = Query(
        default=None,
        description="Event type primary key (required)",
    ),
) -> JSONResponse:
    """Return the full error analysis panel for a device + event type.

    This endpoint orchestrates:
    1. Device and event type metadata lookup
    2. Historical ticket retrieval via the master query (full ticket + device + event data)
    3. Recent raw event logs (error log entries for this device + event type)
    4. Live ping/traceroute/nslookup diagnostics
    5. Gemini LLM-generated hypothesis and recommended steps

    **LLM behaviour when no tickets exist:**
    The LLM still runs and produces an analysis.
    ``suggested_solution.generated_by`` will be ``"no_ticket_llm"`` to signal
    the frontend to display "LLM gave this response" instead of referencing tickets.

    At least one of ``device_id`` or ``device_name`` must be provided,
    along with ``event_type_id``.

    Args:
        current_user: Authenticated user (any role).
        conn: Injected database connection.
        device_id: Device primary key.
        device_name: Partial device name match.
        event_type_id: Event type primary key.

    Returns:
        200 response with full analysis data:
        - ``device``: device info
        - ``event_type``: event type metadata
        - ``historical_info``: tickets (full data) + ``recent_event_logs`` (error log entries)
        - ``preliminary_checks``: ping, traceroute, nslookup
        - ``suggested_solution``: LLM or rule-based analysis with ``has_ticket_context`` flag

    Raises:
        400: If required parameters are missing.
        404: If the device or event type cannot be found.
    """
    if device_id is None and device_name is None:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Provide at least one of: device_id, device_name",
                "data": None,
            },
        )
    if event_type_id is None:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "event_type_id is required",
                "data": None,
            },
        )

    data = await build_error_info(
        conn,
        device_id=device_id,
        device_name=device_name,
        event_type_id=event_type_id,
    )

    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "OK", "data": data},
    )
