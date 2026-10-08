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