"""
LLM service — Gemini API integration for error analysis and suggested solutions.

Uses ``google-generativeai`` to generate structured hypotheses and
recommended remediation steps based on device context, event type,
historical tickets, and diagnostic results.
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
    """Construct the prompt string sent to the Gemini model.

    The prompt asks for structured JSON output with a defined schema.

    Args:
        device: Device row dict.
        event_type: Event type row dict (name, severity, category).
        historical: Historical info dict (total_incidents_6m, related_tickets).
        diagnostics: Preliminary checks dict (ping, traceroute, nslookup).

    Returns:
        A formatted prompt string.
    """
    # Summarise tickets to avoid exceeding context limits
    ticket_summaries = []
    for t in historical.get("related_tickets", [])[:5]:
        ticket_summaries.append(
            f"- [{t.get('ticket_number', 'N/A')}] ({t.get('state', '')}) "
            f"{t.get('short_description', '')[:120]}"
        )

    ticket_text = "\n".join(ticket_summaries) or "No related tickets found."

    # Diagnostic summary
    ping = diagnostics.get("ping", {})
    traceroute = diagnostics.get("traceroute", {})
    nslookup = diagnostics.get("nslookup", {})

    ping_summary = (
        f"Ping: {'REACHABLE' if ping.get('reachable') else 'UNREACHABLE'} "
        f"(loss={ping.get('packet_loss_pct', 'N/A')}%, rtt={ping.get('avg_rtt_ms', 'N/A')}ms)"
    )
    trace_summary = (
        f"Traceroute: {'Completed' if traceroute.get('completed') else 'Failed'} — "
        f"{traceroute.get('error') or 'No error'}"
    )
    dns_summary = (
        f"NSLookup: addresses={nslookup.get('addresses', [])}, "
        f"reverse={nslookup.get('reverse_lookup', 'N/A')}"
    )

    prompt = f"""You are a NOC (Network Operations Center) expert assistant.
Analyze the following network event and provide a structured diagnosis.

## Device Information
- Name: {device.get('device_name', 'N/A')}
- IP Address: {device.get('ip_address', 'N/A')}
- Type: {device.get('machine_type', 'N/A')}
- Vendor: {device.get('vendor', 'N/A')}
- Site: {device.get('site_name', 'N/A')} (Code: {device.get('site_code', 'N/A')})
- Location: {device.get('location', 'N/A')}

## Event Type
- Name: {event_type.get('event_type_name', 'N/A')}
- Severity: {event_type.get('severity', 'N/A')}
- Category: {event_type.get('category', 'N/A')}

## Historical Context
- Total similar incidents (recent): {historical.get('total_incidents_6m', 0)}
- Related ServiceNow Tickets:
{ticket_text}

## Preliminary Network Diagnostics
- {ping_summary}
- {trace_summary}
- {dns_summary}

## Task
Based on the above information, provide a JSON response with EXACTLY this structure:
{{
  "hypothesis": "One-paragraph description of the most likely root cause",
  "recommended_steps": [
    "Step 1: Specific action to take",
    "Step 2: Another specific action",
    "Step 3: Escalation path if steps 1-2 don't resolve"
  ],
  "confidence": "high|medium|low"
}}

Respond with ONLY the JSON object, no markdown fences or extra text.
"""
    return prompt


async def generate_suggested_solution(
    device: dict,
    event_type: dict,
    historical: dict,
    diagnostics: dict,
) -> dict:
    """Call Gemini to generate a hypothesis and recommended steps.

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
        ``generated_by`` keys.
    """
    if not settings.GEMINI_API_KEY:
        logger.info("GEMINI_API_KEY not set — using rule-based fallback")
        return _rule_based_fallback(device, event_type, diagnostics)

    try:
        genai = _get_genai()
        model = genai.GenerativeModel("gemini-1.5-flash")
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
            "hypothesis": parsed.get("hypothesis", "Unable to determine root cause."),
            "recommended_steps": parsed.get("recommended_steps", []),
            "confidence": parsed.get("confidence", "low"),
            "generated_by": "gemini",
        }

    except json.JSONDecodeError as exc:
        logger.warning("Gemini returned non-JSON output: %s", exc)
        return _rule_based_fallback(device, event_type, diagnostics)
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc, exc_info=True)
        return _rule_based_fallback(device, event_type, diagnostics)


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
    category = event_type.get("category", "other")
    severity = event_type.get("severity", "Unknown")
    ping = diagnostics.get("ping", {})
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
        "hypothesis": hypothesis,
        "recommended_steps": steps,
        "confidence": "medium" if reachable else "high",
        "generated_by": "rule-based",
    }
