"""
Tests for the /simulate/logs endpoint.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestSimulationLogs:
    def test_simulate_logs_success(self, client: TestClient, admin_headers: dict):
        """GET /simulate/logs returns 200 with data and meta."""
        resp = client.get("/simulate/logs", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert isinstance(body["data"], list)
        assert "meta" in body

    def test_simulate_logs_unauthenticated(self, client: TestClient):
        """Unauthenticated request returns 401."""
        resp = client.get("/simulate/logs")
        assert resp.status_code == 401

    def test_simulate_logs_count_param(self, client: TestClient, admin_headers: dict):
        """count parameter controls how many logs are returned (up to limit)."""
        resp = client.get(
            "/simulate/logs",
            params={"count": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 5

    def test_simulate_logs_count_max_50(self, client: TestClient, admin_headers: dict):
        """count is capped at 50 even if a higher value is requested."""
        resp = client.get(
            "/simulate/logs",
            params={"count": 200},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_simulate_logs_row_shape(self, client: TestClient, admin_headers: dict):
        """Each returned log row has the expected fields."""
        resp = client.get(
            "/simulate/logs",
            params={"count": 1, "synthetic_ratio": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]
        if rows:
            row = rows[0]
            assert "event_id" in row
            assert "event_type_name" in row or "event_type_id" in row
            assert "severity" in row
            assert "device_name" in row or "device_id" in row
            assert "simulated" in row
            assert row["simulated"] is True

    def test_simulate_logs_meta_fields(self, client: TestClient, admin_headers: dict):
        """The meta block contains total_returned, real_count, synthetic_count."""
        resp = client.get(
            "/simulate/logs",
            params={"count": 10},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        meta = resp.json()["meta"]
        assert "total_returned" in meta

    def test_simulate_logs_analyst_access(self, client: TestClient, analyst_headers: dict):
        """Analyst role can access /simulate/logs (auth required, not admin-only)."""
        resp = client.get("/simulate/logs", headers=analyst_headers)
        assert resp.status_code == 200
