"""
Tests for the /get-logs endpoint.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestLogs:
    def test_get_logs_success(self, client: TestClient, admin_headers: dict):
        """GET /get-logs returns 200 with paginated data."""
        resp = client.get("/get-logs", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        # Backend returns data + meta (not top-level total/page)
        assert "data" in body
        assert isinstance(body["data"], list)
        assert "meta" in body
        meta = body["meta"]
        assert "total" in meta
        assert "page" in meta
        assert "page_size" in meta

    def test_get_logs_unauthenticated(self, client: TestClient):
        """Unauthenticated requests return 401."""
        resp = client.get("/get-logs")
        assert resp.status_code == 401

    def test_get_logs_pagination(self, client: TestClient, admin_headers: dict):
        """Pagination parameters are respected."""
        resp = client.get(
            "/get-logs",
            params={"page": 1, "page_size": 10},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 10
        assert body["meta"]["page"] == 1
        assert body["meta"]["page_size"] == 10

    def test_get_logs_page_2(self, client: TestClient, admin_headers: dict):
        """Page 2 can be requested without error."""
        resp = client.get(
            "/get-logs",
            params={"page": 2, "page_size": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_get_logs_filter_severity(self, client: TestClient, admin_headers: dict):
        """Filtering by severity returns 200 (may return 0 rows if none match)."""
        for severity in ("P1", "P2", "P3", "P4"):
            resp = client.get(
                "/get-logs",
                params={"severity": severity, "page_size": 5},
                headers=admin_headers,
            )
            assert resp.status_code == 200, f"Failed for severity={severity}"

    def test_get_logs_filter_search(self, client: TestClient, admin_headers: dict):
        """Free-text search parameter is accepted."""
        resp = client.get(
            "/get-logs",
            params={"search": "down", "page_size": 5},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_get_logs_event_row_shape(self, client: TestClient, admin_headers: dict):
        """When rows are returned, they contain the required fields."""
        resp = client.get("/get-logs", params={"page_size": 1}, headers=admin_headers)
        assert resp.status_code == 200
        rows = resp.json()["data"]
        if rows:
            row = rows[0]
            assert "event_id" in row
            assert "event_type_name" in row or "event_type_id" in row
            assert "device_id" in row or "device_name" in row

    def test_get_logs_analyst_access(self, client: TestClient, analyst_headers: dict):
        """Analyst role can access /get-logs."""
        resp = client.get("/get-logs", headers=analyst_headers)
        assert resp.status_code == 200
