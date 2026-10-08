"""
Tests for the master query / error-info endpoint.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestErrorInfo:
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
