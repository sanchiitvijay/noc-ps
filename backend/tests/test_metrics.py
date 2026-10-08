"""
Tests for the /get-metrics endpoint.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestMetrics:
    def test_get_metrics_success(self, client: TestClient, admin_headers: dict):
        """GET /get-metrics returns 200 with the expected top-level keys."""
        resp = client.get("/get-metrics", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]

        # The current metrics service returns aggregates, not total device counts.
        assert isinstance(data.get("total_events"), int)
        assert "events_by_severity" in data
        assert "events_by_category" in data
        assert "top_alerting_devices" in data
        assert isinstance(data["top_alerting_devices"], list)

    def test_get_metrics_unauthenticated(self, client: TestClient):
        """Unauthenticated requests return 401."""
        resp = client.get("/get-metrics")
        assert resp.status_code == 401

    def test_get_metrics_time_window_24h(self, client: TestClient, admin_headers: dict):
        """time_window=24h is accepted and returns 200."""
        resp = client.get("/get-metrics", params={"time_window": "24h"}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_get_metrics_time_window_7d(self, client: TestClient, admin_headers: dict):
        """time_window=7d is accepted and returns 200."""
        resp = client.get("/get-metrics", params={"time_window": "7d"}, headers=admin_headers)
        assert resp.status_code == 200

    def test_get_metrics_time_window_30d(self, client: TestClient, admin_headers: dict):
        """time_window=30d is accepted and returns 200."""
        resp = client.get("/get-metrics", params={"time_window": "30d"}, headers=admin_headers)
        assert resp.status_code == 200

    def test_get_metrics_time_window_all(self, client: TestClient, admin_headers: dict):
        """time_window=all is the default and returns 200."""
        resp = client.get("/get-metrics", params={"time_window": "all"}, headers=admin_headers)
        assert resp.status_code == 200

    def test_get_metrics_analyst_access(self, client: TestClient, analyst_headers: dict):
        """Analyst role can also access /get-metrics (not admin-only)."""
        resp = client.get("/get-metrics", headers=analyst_headers)
        assert resp.status_code == 200
