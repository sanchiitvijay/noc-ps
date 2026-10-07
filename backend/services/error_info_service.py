"""
Error info service — orchestrates device lookup, ticket history,
diagnostic checks, and LLM suggestion for the /error-info endpoint.

Lookup priority for suggested_solution:
  1. ticket_solution_summaries table  (cached; instant)
  2. External LLM via llm_service     (Gemini → Groq → rule-based)
"""

from __future__ import annotations

import logging

from database.connection import fetch_one
from services.diagnostic_service import run_all_diagnostics
from services.llm_service import generate_suggested_solution
from services.solution_summary_service import get_summary
from services.ticket_service import get_device_info, get_historical_info
from utils.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def get_event_type(
    conn,
    event_type_id: int,
) -> dict:
    """Fetch event type metadata from event_type_lookup.

    Args:
        conn: Active database connection.
        event_type_id: Primary key of the event type.

    Returns:
        Event type row dict.

    Raises:
        NotFoundError: If the event type does not exist.
    """
    row = await fetch_one(
        conn,
        "SELECT * FROM event_type_lookup WHERE event_type_id = ?",
        (event_type_id,),
    )
    if not row:
        raise NotFoundError("EventType", str(event_type_id))
    return row


async def build_error_info(
    conn,
    device_id: int | None = None,
    device_name: str | None = None,
    event_type_id: int | None = None,
) -> dict:
    """Orchestrate all sub-services and build the full error-info payload.

    Steps:
        1. Resolve the device (by id or name).
        2. Resolve the event type.
        3. Fetch historical ticket + event log info via the master query.
        4. Run ping/traceroute/nslookup diagnostics on the device IP.
        5. Check ticket_solution_summaries for a cached solution.
        6. If no cache hit, generate a solution via LLM (Gemini → Groq → rule-based).

    Args:
        conn: Active database connection.
        device_id: Device primary key (preferred).
        device_name: Device name (used if device_id not provided).
        event_type_id: Event type primary key.

    Returns:
        Full error-info data dict compatible with the ``ErrorInfoData`` schema.
        The ``suggested_solution`` block includes a ``used_saved_summary`` bool
        so the frontend can show "Resolved from saved summary" when applicable.

    Raises:
        NotFoundError: If the device or event type cannot be resolved.
        ValueError: If neither device_id/device_name nor event_type_id is provided.
    """
    if device_id is None and device_name is None:
        raise ValueError("Provide at least one of: device_id, device_name")
    if event_type_id is None:
        raise ValueError("event_type_id is required")

    # Step 1: Resolve device
    device = await get_device_info(conn, device_id=device_id, device_name=device_name)
    if not device:
        identifier = str(device_id or device_name)
        raise NotFoundError("Device", identifier)

    # Step 2: Resolve event type
    event_type = await get_event_type(conn, event_type_id)

    # Step 3: Historical ticket lookup + recent event logs (master query)
    logger.info(
        "Fetching historical info for device_id=%s, event_type_id=%s",
        device["device_id"],
        event_type_id,
    )
    historical = await get_historical_info(conn, device, event_type_id)

    # Step 4: Run all diagnostics on device IP (fall back to device_name if no IP)
    target_host = device.get("ip_address") or device.get("device_name", "127.0.0.1")
    logger.info("Running diagnostics for host=%s", target_host)
    diagnostics = await run_all_diagnostics(target_host)

    # Step 5: Check saved solution summary cache (fast path)
    saved_summary = await get_summary(conn, device["device_id"], event_type_id)
    if saved_summary:
        logger.info(
            "Found saved solution summary for device_id=%s event_type_id=%s",
            device["device_id"],
            event_type_id,
        )

    # Step 6: LLM suggestion — pass saved_summary so it can be injected into prompt
    logger.info("Generating LLM suggestion (saved_summary=%s)", saved_summary is not None)
    suggestion = await generate_suggested_solution(
        device=device,
        event_type=event_type,
        historical=historical,
        diagnostics=diagnostics,
        saved_summary=saved_summary,
    )

    return {
        "device":             device,
        "event_type":         event_type,
        "historical_info":    historical,
        "preliminary_checks": diagnostics,
        "suggested_solution": suggestion,
    }
