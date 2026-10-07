"""
Tests for the master query / error-info endpoint.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestErrorInfo:
    def test_get_error_info_success(self, client: TestClient, admin_headers: dict):
        # Using device_id 1 and event_type_id 1 (Node Down on a simulation device)
        resp = client.get(
            "/error-info",
            params={"device_id": 1, "event_type_id": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 200
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
            params={"device_id": 1},  # missing event_type_id
            headers=admin_headers,
        )
        assert resp.status_code == 400

        resp = client.get(
            "/error-info",
            params={"event_type_id": 1},  # missing device_id/device_name
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_get_error_info_device_name_fallback(self, client: TestClient, admin_headers: dict):
        # In a real test database, we would seed a specific device.
        # This will either return 200 (if found) or 404 (if not).
        resp = client.get(
            "/error-info",
            params={"device_name": "NonExistentDevice123", "event_type_id": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_error_info_requires_auth(self, client: TestClient):
        resp = client.get(
            "/error-info",
            params={"device_id": 1, "event_type_id": 1},
        )
        assert resp.status_code == 401
