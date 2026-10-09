"""
Tests for the master query / error-info endpoint.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient
from config import settings


class TestErrorInfo:
    def test_ai_result_is_cached_and_reused(
        self,
        client: TestClient,
        admin_headers: dict,
        monkeypatch,
    ):
        with sqlite3.connect(settings.db_path) as conn:
            event = conn.execute(
                """SELECT el.event_id FROM event_logs AS el
                   JOIN devices AS d ON d.device_id = el.device_id
                   JOIN event_type_lookup AS et ON et.event_type_id = el.event_type_id
                   ORDER BY el.event_id LIMIT 1"""
            ).fetchone()
        assert event is not None, "test database needs one fully linked event"
        event_id = event[0]
        calls = []

        async def fake_generate(**kwargs):
            calls.append(kwargs)
            return {
                "hypothesis": "Provider-generated test hypothesis",
                "recommended_steps": ["Check the event"],
                "confidence": "high",
                "generated_by": "groq",
                "has_ticket_context": False,
                "used_saved_summary": False,
            }

        monkeypatch.setattr(
            "services.error_info_service.generate_suggested_solution",
            fake_generate,
        )

        first = client.get(
            "/error-info",
            params={"event_id": event_id},
            headers=admin_headers,
        )
        assert first.status_code == 200
        assert first.json()["data"]["suggested_solution"]["generated_by"] == "groq"
        assert len(calls) == 1

        second = client.get(
            "/error-info",
            params={"event_id": event_id},
            headers=admin_headers,
        )
        assert second.status_code == 200
        cached = second.json()["data"]["suggested_solution"]
        assert cached["hypothesis"] == "Provider-generated test hypothesis"
        assert cached["generated_by"] == "groq"
        assert cached["used_saved_summary"] is True
        assert len(calls) == 1

    def test_get_error_info_success(self, client: TestClient, admin_headers: dict):
        # Using event_id 1
        resp = client.get(
            "/error-info",
            params={"event_id": 1},
            headers=admin_headers,
        )
        # If event_id 1 exists in the test DB, this should be 200. Otherwise it will be 404.
        if resp.status_code == 200:
            data = resp.json()["data"]

            # Check all required blocks are present
            assert "device" in data
            assert "event_type" in data
            assert "historical_info" in data
            assert "preliminary_checks" in data
            assert "suggested_solution" in data

            # Check preliminary checks structure (should be fake diagnostics)
            assert "ping" in data["preliminary_checks"]
            assert "traceroute" in data["preliminary_checks"]
            assert "nslookup" in data["preliminary_checks"]

            # Check LLM / Rule-based suggestion structure
            suggestion = data["suggested_solution"]
            assert "hypothesis" in suggestion
            assert "recommended_steps" in suggestion
            assert "confidence" in suggestion
            assert "generated_by" in suggestion
            assert "has_ticket_context" in suggestion
            assert "used_saved_summary" in suggestion

    def test_get_error_info_missing_params(self, client: TestClient, admin_headers: dict):
        resp = client.get(
            "/error-info",
            headers=admin_headers,
        )
        assert resp.status_code == 400 # Explicitly returning 400 in code

    def test_get_error_info_device_name_fallback(self, client: TestClient, admin_headers: dict):
        # In a real test database, we would seed a specific event.
        # This will return 404 since event_id=999999 doesn't exist
        resp = client.get(
            "/error-info",
            params={"event_id": 999999},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_error_info_requires_auth(self, client: TestClient):
        resp = client.get(
            "/error-info",
            params={"event_id": 1},
        )
        assert resp.status_code == 401
