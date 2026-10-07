"""
Internal diagnostics router — /internal/ping, /internal/traceroute, /internal/nslookup.

All routes require a valid JWT (any authenticated user — same access level as /error-info).
Analyst/Admin-only restriction has been removed so any logged-in user can run diagnostics
directly. Dispatches to diagnostic_service which handles both fake (default) and real
system commands based on FAKE_DIAGNOSTICS setting.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from routers.dependencies import get_current_user
from schemas.ingest import DiagnosticRequest
from services.diagnostic_service import run_nslookup, run_ping, run_traceroute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal Diagnostics"])


@router.post(
    "/ping",
    summary="Run a ping diagnostic against a host",
    responses={
        200: {"description": "Ping result with packet loss and RTT metrics"},
        400: {"description": "Invalid request body"},
        401: {"description": "Authentication required"},
        500: {"description": "Diagnostic command failed"},
    },
)
async def ping(
    body: DiagnosticRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> JSONResponse:
    """Send ICMP echo requests to a host and return packet loss and RTT metrics.

    When ``FAKE_DIAGNOSTICS=True`` (default), returns a mocked result:
    - Hosts in 10.x.x.x / private IP ranges → 100% packet loss
    - All other hosts → 0% packet loss with 12.4ms RTT

    When ``FAKE_DIAGNOSTICS=False``, runs the system ``ping`` command.

    Args:
        body: DiagnosticRequest with host and optional count.
        current_user: Any authenticated user.

    Returns:
        200 response with ping result dict.

    Raises:
        500: If the diagnostic command fails unexpectedly.
    """
    try:
        result = await run_ping(body.host, body.count)
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "OK", "data": result},
        )
    except Exception as exc:
        logger.error("ping failed for host=%s: %s", body.host, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ping diagnostic failed: {exc}") from exc


@router.post(
    "/traceroute",
    summary="Run a traceroute against a host",
    responses={
        200: {"description": "Traceroute result including hop-by-hop RTT"},
        400: {"description": "Invalid request body"},
        401: {"description": "Authentication required"},
        500: {"description": "Diagnostic command failed"},
    },
)
async def traceroute(
    body: DiagnosticRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> JSONResponse:
    """Trace the network path to a host, showing each hop's RTT.

    When ``FAKE_DIAGNOSTICS=True``, returns a mocked traceroute with a
    simulated failure at hop 3 (useful for demo scenarios).

    Args:
        body: DiagnosticRequest with host.
        current_user: Any authenticated user.

    Returns:
        200 response with traceroute result including hops list.

    Raises:
        500: If the diagnostic command fails unexpectedly.
    """
    try:
        result = await run_traceroute(body.host)
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "OK", "data": result},
        )
    except Exception as exc:
        logger.error("traceroute failed for host=%s: %s", body.host, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Traceroute diagnostic failed: {exc}") from exc


@router.post(
    "/nslookup",
    summary="Run a DNS lookup against a host",
    responses={
        200: {"description": "DNS lookup result with resolved addresses and reverse lookup"},
        400: {"description": "Invalid request body"},
        401: {"description": "Authentication required"},
        500: {"description": "Diagnostic command failed"},
    },
)
async def nslookup(
    body: DiagnosticRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> JSONResponse:
    """Perform a DNS forward and reverse lookup for a host.

    When ``FAKE_DIAGNOSTICS=True``, returns plausible mocked DNS data.

    Args:
        body: DiagnosticRequest with host (IP or hostname).
        current_user: Any authenticated user.

    Returns:
        200 response with resolved addresses and reverse lookup name.

    Raises:
        500: If the diagnostic command fails unexpectedly.
    """
    try:
        result = await run_nslookup(body.host)
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "OK", "data": result},
        )
    except Exception as exc:
        logger.error("nslookup failed for host=%s: %s", body.host, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"NSLookup diagnostic failed: {exc}") from exc
