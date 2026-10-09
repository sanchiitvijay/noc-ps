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
    event_id: int,
) -> dict:
    """Orchestrate all sub-services and build the full error-info payload.

    Steps:
        1. Resolve the event log from event_id to get device_id and event_type_id.
        2. Resolve the device.
        3. Resolve the event type.
        4. Fetch historical ticket + event log info via the master query.
        5. Run ping/traceroute/nslookup diagnostics on the device IP.
        6. Check ticket_solution_summaries for a cached solution.
        7. If no cache hit, generate a solution via LLM (Gemini → Groq → rule-based).

    Args:
        conn: Active database connection.
        event_id: Event primary key.

    Returns:
        Full error-info data dict compatible with the ``ErrorInfoData`` schema.
        The ``suggested_solution`` block includes a ``used_saved_summary`` bool
        so the frontend can show "Resolved from saved summary" when applicable.

    Raises:
        NotFoundError: If the event, device or event type cannot be resolved.
        ValueError: If event_id is not provided.
    """
    if event_id is None:
        raise ValueError("event_id is required")

    # Step 0: Resolve event from event_logs to get device_id and event_type_id
    event_row = await fetch_one(
        conn,
        "SELECT device_id, event_type_id FROM event_logs WHERE event_id = ?",
        (event_id,)
    )
    if not event_row:
        raise NotFoundError("EventLog", str(event_id))
        
    device_id = event_row["device_id"]
    event_type_id = event_row["event_type_id"]

    # Step 1: Resolve device
    device = await get_device_info(conn, device_id=device_id)
    if not device:
        identifier = str(device_id)
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
    saved_summary = await get_summary(conn, event_id)
    if saved_summary:
        logger.info(
            "Found saved solution summary for event_id=%s",
            event_id,
        )

    cached_provider = saved_summary.get("generated_by") if saved_summary else None
    retry_rule_based = saved_summary is not None and cached_provider == "rule-based"

    # Fresh AI/analyst summaries are cache hits. Rule-based summaries are a
    # fallback cache only, so retry configured providers before returning them.
    if saved_summary and not retry_rule_based:
        suggestion = {
            "hypothesis": saved_summary["hypothesis"],
            "recommended_steps": saved_summary["recommended_steps"],
            "confidence": saved_summary["confidence"],
            "generated_by": saved_summary.get("generated_by", "saved-summary"),
            "has_ticket_context": bool(historical.get("related_tickets")),
            "used_saved_summary": True,
        }
    else:
        logger.info(
            "Generating LLM suggestion (saved_summary=%s, retry_rule_based=%s)",
            saved_summary is not None,
            retry_rule_based,
        )
        suggestion = await generate_suggested_solution(
            device=device,
            event_type=event_type,
            historical=historical,
            diagnostics=diagnostics,
            saved_summary=saved_summary,
        )

    # Upgrade a rule-based fallback when an AI provider becomes available.
    if suggestion.get("generated_by") in ("gemini", "groq") and (
        not saved_summary or retry_rule_based
    ):
        try:
            from services.solution_summary_service import upsert_summary  # noqa: PLC0415
            ticket_numbers = [
                t.get("ticket_number")
                for t in historical.get("related_tickets", [])
                if t.get("ticket_number")
            ]
            await upsert_summary(
                conn,
                event_id=event_id,
                hypothesis=suggestion.get("hypothesis", ""),
                recommended_steps=suggestion.get("recommended_steps", []),
                confidence=suggestion.get("confidence", "medium"),
                generated_by=suggestion["generated_by"],
                source_tickets=ticket_numbers or None,
            )
            logger.info(
                "Cached LLM result for event_id=%s (provider=%s)",
                event_id,
                suggestion["generated_by"],
            )
        except Exception as cache_exc:  # pragma: no cover
            logger.warning("Failed to cache LLM result: %s", cache_exc)
    elif retry_rule_based and saved_summary:
        suggestion = {
            "hypothesis": saved_summary["hypothesis"],
            "recommended_steps": saved_summary["recommended_steps"],
            "confidence": saved_summary["confidence"],
            "generated_by": cached_provider,
            "has_ticket_context": bool(historical.get("related_tickets")),
            "used_saved_summary": True,
        }

    return {
        "device":             device,
        "event_type":         event_type,
        "historical_info":    historical,
        "preliminary_checks": diagnostics,
        "suggested_solution": suggestion,
    }
