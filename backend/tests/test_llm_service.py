import asyncio
import json
from types import SimpleNamespace

import services.llm_service as llm_service


def test_groq_call_uses_available_model_and_parses_json(monkeypatch):
    request = {}

    def create_completion(**kwargs):
        request.update(kwargs)
        message = SimpleNamespace(
            content=json.dumps({
                "hypothesis": "Test hypothesis",
                "recommended_steps": ["Verify the link"],
                "confidence": "high",
            })
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_completion),
        ),
    )
    monkeypatch.setattr(llm_service, "_get_groq", lambda: client)

    result = asyncio.run(llm_service._call_groq("test prompt"))

    assert request["model"] == "openai/gpt-oss-20b"
    assert result["hypothesis"] == "Test hypothesis"
    assert result["recommended_steps"] == ["Verify the link"]


def test_gemini_failure_falls_back_to_groq(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "GEMINI_API_KEY", "configured")
    monkeypatch.setattr(llm_service.settings, "GROQ_API_KEY", "configured")

    async def fail_gemini(prompt):
        raise RuntimeError("simulated Gemini outage")

    async def return_groq(prompt):
        return {
            "hypothesis": "Groq hypothesis",
            "recommended_steps": ["Verify the link"],
            "confidence": "high",
        }

    monkeypatch.setattr(llm_service, "_call_gemini", fail_gemini)
    monkeypatch.setattr(llm_service, "_call_groq", return_groq)

    result = asyncio.run(
        llm_service.generate_suggested_solution(
            device={},
            event_type={},
            historical={},
            diagnostics={},
        )
    )

    assert result["generated_by"] == "groq"
    assert result["hypothesis"] == "Groq hypothesis"


def test_build_prompt_includes_ticket_work_notes():
    device = {"device_name": "switch-01", "ip_address": "10.0.0.1", "machine_type": "Switch"}
    event_type = {"event_type_name": "Interface Down", "severity": "P1", "category": "interface"}
    historical = {
        "total_incidents_6m": 2,
        "related_tickets": [
            {
                "ticket_number": "INC001",
                "state": "Resolved",
                "short_description": "Port Gi1/0/1 went down",
                "work_notes": "01-15-2026 - Replaced bad fiber cable. Link restored.",
            },
            {
                "ticket_number": "INC002",
                "state": "Closed",
                "short_description": "Transceiver failure",
                "work_notes": None,
            },
        ],
    }
    diagnostics = {"ping": {"reachable": True, "packet_loss_pct": 0, "avg_rtt_ms": 1.5}}

    prompt = llm_service._build_prompt(device, event_type, historical, diagnostics)

    assert "Work notes: 01-15-2026 - Replaced bad fiber cable. Link restored." in prompt
    assert "[INC001] state=Resolved — Port Gi1/0/1 went down" in prompt
    assert "[INC002] state=Closed — Transceiver failure" in prompt
    # INC002 had no work notes, so ensure it doesn't print "Work notes: None"
    assert "Work notes: None" not in prompt


def test_build_prompt_includes_explicit_work_notes():
    device = {"device_name": "router-01", "ip_address": "10.0.0.2", "machine_type": "Router"}
    event_type = {"event_type_name": "Node Down", "severity": "P1", "category": "device"}
    historical = {"total_incidents_6m": 1, "related_tickets": []}
    diagnostics = {"ping": {"reachable": False}}

    prompt = llm_service._build_prompt(
        device,
        event_type,
        historical,
        diagnostics,
        work_notes="Field technician verified power outage at site.",
    )

    assert "Work notes:\n  Field technician verified power outage at site." in prompt


def test_gemini_call_receives_work_notes(monkeypatch):
    monkeypatch.setattr(llm_service.settings, "GEMINI_API_KEY", "configured")

    captured_prompt = {}

    async def fake_gemini(prompt):
        captured_prompt["prompt"] = prompt
        return {
            "hypothesis": "Cable issue identified from work notes",
            "recommended_steps": ["Check the fiber cable"],
            "confidence": "high",
        }

    monkeypatch.setattr(llm_service, "_call_gemini", fake_gemini)

    historical = {
        "related_tickets": [
            {
                "ticket_number": "INC999",
                "state": "Resolved",
                "short_description": "Uplink flap",
                "work_notes": "Cleaned optical transceiver pins.",
            }
        ]
    }

    result = asyncio.run(
        llm_service.generate_suggested_solution(
            device={"device_name": "leaf-1"},
            event_type={"event_type_name": "Link Flap"},
            historical=historical,
            diagnostics={},
        )
    )

    assert result["generated_by"] == "gemini"
    assert result["hypothesis"] == "Cable issue identified from work notes"
    assert "Work notes: Cleaned optical transceiver pins." in captured_prompt["prompt"]