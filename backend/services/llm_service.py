"""
LLM service — Gemini API integration for error analysis and suggested solutions.

Sends only minimal, essential context to Gemini (device type, event, ping
status, ticket count + up to 3 ticket snippets) to minimise token usage.

If LLM is unavailable or returns an error, falls back gracefully to a
rule-based suggestion. If there are no related tickets the response is
clearly labelled as an LLM-only analysis.
"""

from __future__ import annotations

import json
import logging

from config import settings

logger = logging.getLogger(__name__)

# Lazy import to avoid startup failure when GEMINI_API_KEY is empty
_genai = None


def _get_genai():
    """Lazily import and configure the google.generativeai module.

    Returns:
        The configured ``google.generativeai`` module instance.

    Raises:
        ImportError: If the package is not installed.
        ValueError: If GEMINI_API_KEY is not configured.
    """
    global _genai
    if _genai is None:
        import google.generativeai as genai  # noqa: PLC0415

        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not configured. "
                "Set it in the .env file to enable AI-powered suggestions."
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _genai = genai
    return _genai


def _build_prompt(
    device: dict,
    event_type: dict,
    historical: dict,
    diagnostics: dict,
) -> str:
    """Construct a *minimal* prompt for Gemini — only essential fields.

    We deliberately omit large blobs (description, work_notes, raw_detail,
    traceroute hops, nslookup details) to keep the context small and fast.

    Args:
        device: Device row dict.
        event_type: Event type row dict (name, severity, category).
        historical: Historical info dict (total_incidents_6m, related_tickets).
        diagnostics: Preliminary checks dict (ping only — rest stripped).

    Returns:
        A compact prompt string.
    """
    tickets = historical.get("related_tickets", [])
    has_tickets = bool(tickets)

    # Up to 3 tickets — only number, state, short_description (max 100 chars)
    ticket_lines: list[str] = []
    for t in tickets[:3]:
        desc = (t.get("short_description") or "")[:100]
        ticket_lines.append(
            f"  [{t.get('ticket_number', 'N/A')}] state={t.get('state', '?')} — {desc}"
        )
    ticket_text = "\n".join(ticket_lines) if ticket_lines else "None found."

    # Ping summary only (most actionable diagnostic signal)
    ping = diagnostics.get("ping", {})
    ping_status = "REACHABLE" if ping.get("reachable") else "UNREACHABLE"
    ping_loss   = ping.get("packet_loss_pct", "N/A")
    ping_rtt    = ping.get("avg_rtt_ms", "N/A")

    no_ticket_note = (
        "\nNOTE: No historical tickets exist for this device. "
        "Your analysis must be based purely on the event type and diagnostic results.\n"
        if not has_tickets else ""
    )

    prompt = f"""You are a NOC expert assistant. Diagnose the following network event concisely.
{no_ticket_note}
Device: {device.get('device_name', 'N/A')} | IP: {device.get('ip_address', 'N/A')} | Type: {device.get('machine_type', 'N/A')}
Event: {event_type.get('event_type_name', 'N/A')} | Severity: {event_type.get('severity', 'N/A')} | Category: {event_type.get('category', 'N/A')}
Incidents (recent): {historical.get('total_incidents_6m', 0)}
Ping: {ping_status} (loss={ping_loss}%, rtt={ping_rtt}ms)
Related tickets:
{ticket_text}

Respond ONLY with this JSON (no markdown):
{{
  "hypothesis": "One paragraph root cause",
  "recommended_steps": ["Step 1", "Step 2", "Step 3"],
  "confidence": "high|medium|low"
}}"""
    return prompt


async def generate_suggested_solution(
    device: dict,
    event_type: dict,
    historical: dict,
    diagnostics: dict,
) -> dict:
    """Call Gemini to generate a hypothesis and recommended steps.

    If there are no related tickets, the response will be clearly flagged
    as ``"no_ticket_llm"`` source so the frontend can show the appropriate
    label (e.g. "LLM gave this response").

    Falls back to a rule-based suggestion if the API key is missing or if
    the API call fails, so the endpoint never returns an error purely due
    to LLM unavailability.

    Args:
        device: Device row dict.
        event_type: Event type row dict.
        historical: Historical info dict from ticket_service.
        diagnostics: Diagnostic results dict from diagnostic_service.

    Returns:
        Dict with ``hypothesis``, ``recommended_steps``, ``confidence``,
        ``generated_by``, and ``has_ticket_context`` keys.
    """
    has_tickets = bool(historical.get("related_tickets"))

    if not settings.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY not set — using rule-based fallback")
        result = _rule_based_fallback(device, event_type, diagnostics)
        result["has_ticket_context"] = has_tickets
        return result

    try:
        genai  = _get_genai()
        model  = genai.GenerativeModel("gemini-3.5-flash")
        prompt = _build_prompt(device, event_type, historical, diagnostics)

        response = model.generate_content(prompt)
        raw_text = response.text.strip()

        # Strip markdown fences if the model added them despite instructions
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        parsed = json.loads(raw_text)
        return {
            "hypothesis":        parsed.get("hypothesis", "Unable to determine root cause."),
            "recommended_steps": parsed.get("recommended_steps", []),
            "confidence":        parsed.get("confidence", "low"),
            # "no_ticket_llm" signals to the frontend to show "LLM gave this response"
            "generated_by":      "gemini" if has_tickets else "no_ticket_llm",
            "has_ticket_context": has_tickets,
        }

    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned non-JSON output: %s", exc)
        result = _rule_based_fallback(device, event_type, diagnostics)
        result["has_ticket_context"] = has_tickets
        return result
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc, exc_info=True)
        result = _rule_based_fallback(device, event_type, diagnostics)
        result["has_ticket_context"] = has_tickets
        return result


def _rule_based_fallback(device: dict, event_type: dict, diagnostics: dict) -> dict:
    """Generate a basic rule-based suggestion when the LLM is unavailable.

    Uses the event category and ping result to produce a minimal but useful
    recommendation.

    Args:
        device: Device row dict.
        event_type: Event type row dict.
        diagnostics: Diagnostic results dict.

    Returns:
        Suggestion dict with ``generated_by="rule-based"``.
    """
    category  = event_type.get("category", "other")
    severity  = event_type.get("severity", "Unknown")
    ping      = diagnostics.get("ping", {})
    reachable = ping.get("reachable", True)

    if not reachable:
        hypothesis = (
            f"Device '{device.get('device_name')}' is not responding to ping. "
            f"The {severity} {category} event suggests a connectivity or power issue."
        )
        steps = [
            "Verify physical connectivity — check port lights and cable integrity.",
            "Check upstream switch/router for interface errors or port shutdown.",
            "Attempt console access if the device is completely unresponsive.",
            "If remote site, contact on-site personnel to perform physical inspection.",
            "Escalate to network team if issue persists beyond 30 minutes.",
        ]
    elif category == "interface":
        hypothesis = (
            f"Interface errors detected on '{device.get('device_name')}'. "
            "Possible causes include duplex mismatch, cable quality issues, or high traffic."
        )
        steps = [
            "Check interface error counters (input/output errors, CRC, drops).",
            "Verify duplex and speed settings match the connected device.",
            "Inspect cable quality or replace patch cable.",
            "Monitor interface utilization — consider QoS if bandwidth saturation detected.",
        ]
    elif category == "performance":
        hypothesis = (
            f"Performance degradation on '{device.get('device_name')}'. "
            "High CPU, memory, or link utilization may be the root cause."
        )
        steps = [
            "Check CPU and memory utilization via SNMP or device CLI.",
            "Identify top traffic flows using NetFlow/sFlow if available.",
            "Review QoS policies for rate limiting or queuing issues.",
            "Consider a scheduled maintenance window for optimization.",
        ]
    elif category == "wireless":
        hypothesis = (
            f"Wireless issue on '{device.get('device_name')}'. "
            "RF interference, channel congestion, or AP hardware failure are likely causes."
        )
        steps = [
            "Check AP channel utilization and switch to a less congested channel.",
            "Verify AP power levels and client association counts.",
            "Check for RF interference sources in the area.",
            "Reboot the AP if clients are unable to associate.",
        ]
    else:
        hypothesis = (
            f"A {severity} event of type '{event_type.get('event_type_name')}' "
            f"was detected on device '{device.get('device_name')}'. "
            "Manual investigation required."
        )
        steps = [
            "Review the device logs for related error messages.",
            "Check recent configuration changes via change management records.",
            "Verify device health metrics (CPU, memory, interface status).",
            "Escalate to the appropriate team based on device type and severity.",
        ]

    return {
        "hypothesis":        hypothesis,
        "recommended_steps": steps,
        "confidence":        "medium" if reachable else "high",
        "generated_by":      "rule-based",
    }
