"""
LLM service — Gemini API integration for error analysis and suggested solutions.

Fallback chain:
  1. Gemini (primary — google.generativeai)
    2. Groq  (fallback — groq SDK, model: openai/gpt-oss-20b)
  3. Rule-based (final fallback — always succeeds)

Sends only minimal, essential context to the LLM (device type, event, ping
status, ticket count + up to 3 ticket snippets) to minimise token usage.

If a saved ticket solution summary exists for the device+event_type combination,
it is injected into the prompt so the LLM can reference it directly.
"""

from __future__ import annotations

import json
import logging

from config import settings

logger = logging.getLogger(__name__)
GROQ_MODEL = "openai/gpt-oss-20b"

# Lazy singletons to avoid startup failures when API keys are absent
_genai = None
_groq_client = None


# ---------------------------------------------------------------------------
# Client initialisation helpers
# ---------------------------------------------------------------------------


def _get_genai():
    """Lazily import and configure google.generativeai.

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
                "Set it in the .env file to enable Gemini AI suggestions."
            )
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _genai = genai
    return _genai


def _get_groq():
    """Lazily import and configure the Groq client.

    Returns:
        A configured ``groq.Groq`` client.

    Raises:
        ImportError: If the ``groq`` package is not installed.
        ValueError: If GROQ_API_KEY is not configured.
    """
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "groq package not installed. Run: pip install groq"
            ) from exc

        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")

        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _build_prompt(
    device: dict,
    event_type: dict,
    historical: dict,
    diagnostics: dict,
    saved_summary: dict | None = None,
) -> str:
    """Construct a *minimal* prompt — only essential fields.

    We deliberately omit large blobs (full description, work_notes,
    raw_detail, traceroute hops, nslookup details) to keep the context
    small and fast.

    Args:
        device: Device row dict.
        event_type: Event type row dict (name, severity, category).
        historical: Historical info dict (total_incidents_6m, related_tickets).
        diagnostics: Preliminary checks dict.
        saved_summary: Optional pre-computed ticket solution summary from DB.

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

    # Inject saved summary if available
    saved_summary_block = ""
    if saved_summary:
        saved_summary_block = f"""
Known solution summary (pre-computed from past tickets):
  Hypothesis: {saved_summary.get('hypothesis', 'N/A')}
  Steps: {'; '.join(saved_summary.get('recommended_steps', []))}
  Confidence: {saved_summary.get('confidence', 'N/A')}
Use this as a strong reference but still validate against current diagnostics.
"""

    prompt = f"""You are a NOC expert assistant. Diagnose the following network event concisely.
{no_ticket_note}{saved_summary_block}
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


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------


def _parse_llm_response(raw_text: str) -> dict:
    """Parse and clean an LLM JSON response, stripping any markdown fences.

    Args:
        raw_text: Raw text returned by the LLM.

    Returns:
        Parsed dict with hypothesis, recommended_steps, confidence.

    Raises:
        json.JSONDecodeError: If the text cannot be parsed as JSON.
    """
    text = raw_text.strip()
    # Strip markdown fences if present despite instructions
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


async def _call_gemini(prompt: str) -> dict:
    """Call the Gemini API and return parsed JSON.

    Args:
        prompt: The prompt string.

    Returns:
        Parsed dict with hypothesis, recommended_steps, confidence.

    Raises:
        Exception: On API or parse failure.
    """
    genai = _get_genai()
    model = genai.GenerativeModel("gemini-3.5-flash")
    response = model.generate_content(prompt)
    return _parse_llm_response(response.text)


async def _call_groq(prompt: str) -> dict:
    """Call the Groq API using the configured account's available model."""
    client = _get_groq()
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a NOC expert assistant. "
                    "Always respond ONLY with valid JSON — no markdown, no extra text."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=512,
    )
    raw = completion.choices[0].message.content or ""
    return _parse_llm_response(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_suggested_solution(
    device: dict,
    event_type: dict,
    historical: dict,
    diagnostics: dict,
    saved_summary: dict | None = None,
) -> dict:
    """Generate a hypothesis and recommended steps.

    Fallback chain: Gemini → Groq → Rule-based.

    If a ``saved_summary`` is provided (from the ticket_solution_summaries table),
    it is injected into the prompt and also returned in the response so the frontend
    knows a cached solution exists.

    Args:
        device: Device row dict.
        event_type: Event type row dict.
        historical: Historical info dict from ticket_service.
        diagnostics: Diagnostic results dict from diagnostic_service.
        saved_summary: Optional pre-computed summary dict from DB.

    Returns:
        Dict with ``hypothesis``, ``recommended_steps``, ``confidence``,
        ``generated_by``, ``has_ticket_context``, and ``used_saved_summary``
        keys.
    """
    has_tickets = bool(historical.get("related_tickets"))
    prompt = _build_prompt(device, event_type, historical, diagnostics, saved_summary)

    def _wrap(parsed: dict, source: str) -> dict:
        return {
            "hypothesis":        parsed.get("hypothesis", "Unable to determine root cause."),
            "recommended_steps": parsed.get("recommended_steps", []),
            "confidence":        parsed.get("confidence", "low"),
            "generated_by":      source,
            "has_ticket_context": has_tickets,
            "used_saved_summary": saved_summary is not None,
        }

    # ── 1. Gemini (primary) ────────────────────────────────────────────────────
    if settings.GEMINI_API_KEY:
        try:
            parsed = await _call_gemini(prompt)
            logger.info("LLM response generated by Gemini")
            return _wrap(parsed, "gemini")
        except json.JSONDecodeError as exc:
            logger.warning("Gemini returned non-JSON output: %s", exc)
        except Exception as exc:
            logger.warning("Gemini API call failed (%s) — trying Groq fallback", exc)
    else:
        logger.info("GEMINI_API_KEY not set — skipping Gemini")

    # ── 2. Groq fallback ──────────────────────────────────────────────────────
    if settings.GROQ_API_KEY:
        try:
            parsed = await _call_groq(prompt)
            logger.info("LLM response generated by Groq (fallback)")
            return _wrap(parsed, "groq")
        except json.JSONDecodeError as exc:
            logger.warning("Groq returned non-JSON output: %s", exc)
        except Exception as exc:
            logger.warning("Groq API call failed (%s) — using rule-based fallback", exc)
    else:
        logger.info("GROQ_API_KEY not set — skipping Groq fallback")

    # ── 3. Rule-based fallback (always succeeds) ──────────────────────────────
    logger.info("Using rule-based fallback suggestion")
    result = _rule_based_fallback(device, event_type, diagnostics)
    result["has_ticket_context"] = has_tickets
    result["used_saved_summary"] = saved_summary is not None
    return result


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------


def _rule_based_fallback(device: dict, event_type: dict, diagnostics: dict) -> dict:
    """Generate a basic rule-based suggestion when both LLMs are unavailable.

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
    severity  = event_type.get("severity")
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
