"""
Internal diagnostics router — /internal/ping, /internal/traceroute, /internal/nslookup.

Requires analyst or admin role. Dispatches to diagnostic_service which handles
both fake (default) and real system commands based on FAKE_DIAGNOSTICS setting.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from routers.dependencies import require_analyst_or_admin
from schemas.ingest import DiagnosticRequest
from services.diagnostic_service import run_nslookup, run_ping, run_traceroute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["Internal Diagnostics"])


@router.post("/ping", summary="Run a ping diagnostic against a host")
async def ping(
    body: DiagnosticRequest,
    current_user: Annotated[dict, Depends(require_analyst_or_admin)],
) -> JSONResponse:
    """Send ICMP echo requests to a host and return packet loss and RTT metrics.

    When ``FAKE_DIAGNOSTICS=True`` (default), returns a mocked result:
    - Hosts in 10.x.x.x / private IP ranges → 100% packet loss
    - All other hosts → 0% packet loss with 12.4ms RTT

    When ``FAKE_DIAGNOSTICS=False``, runs the system ``ping`` command.

    Args:
        body: DiagnosticRequest with host and optional count.
        current_user: Authenticated analyst or admin.

    Returns:
        200 response with ping result dict.
    """
    result = await run_ping(body.host, body.count)
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "OK", "data": result},
    )


@router.post("/traceroute", summary="Run a traceroute against a host")
async def traceroute(
    body: DiagnosticRequest,
    current_user: Annotated[dict, Depends(require_analyst_or_admin)],
) -> JSONResponse:
    """Trace the network path to a host, showing each hop's RTT.

    When ``FAKE_DIAGNOSTICS=True``, returns a mocked traceroute with a
    simulated failure at hop 3 (useful for demo scenarios).

    Args:
        body: DiagnosticRequest with host.
        current_user: Authenticated analyst or admin.

    Returns:
        200 response with traceroute result including hops list.
    """
    result = await run_traceroute(body.host)
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "OK", "data": result},
    )


@router.post("/nslookup", summary="Run a DNS lookup against a host")
async def nslookup(
    body: DiagnosticRequest,
    current_user: Annotated[dict, Depends(require_analyst_or_admin)],
) -> JSONResponse:
    """Perform a DNS forward and reverse lookup for a host.

    When ``FAKE_DIAGNOSTICS=True``, returns plausible mocked DNS data.

    Args:
        body: DiagnosticRequest with host (IP or hostname).
        current_user: Authenticated analyst or admin.

    Returns:
        200 response with resolved addresses and reverse lookup name.
    """
    result = await run_nslookup(body.host)
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "OK", "data": result},
    )
