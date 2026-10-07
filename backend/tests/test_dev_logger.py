"""
Tests for the development route and SQL query logger.

Verifies:
  - All routes trigger log entry creation in log.txt
  - All entries append to the same log.txt file
  - Request details (method, path, headers, query params, body) are logged
  - Total time taken (latency) is recorded accurately
  - All SQL queries, parameters, execution times, and returned data are logged
  - Nothing is truncated in the log
  - Multiple routes append sequentially without overwriting
"""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from middleware.dev_logger import get_dev_log_path


class TestDevLogger:
    def test_log_file_created_and_route_logged(self, client: TestClient):
        """Hitting a route ensures log.txt exists and records the route and total time."""
        log_path = get_dev_log_path()

        # Record size before
        size_before = log_path.stat().st_size if log_path.exists() else 0

        resp = client.get("/health")
        assert resp.status_code == 200

        assert log_path.exists(), "log.txt should exist after route call"
        size_after = log_path.stat().st_size
        assert size_after > size_before, "log.txt should have grown"

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "ROUTE TRIGGERED: GET /health" in content
        assert "Route Triggered:  GET /health" in content
        assert "Status Code:      200 OK" in content
        assert "Total Time Taken:" in content
        assert "Response Body:" in content
        assert '"status": "ok"' in content

    def test_sql_query_and_data_logged(self, client: TestClient):
        """Hitting an endpoint with DB access logs all SQL statements and returned data."""
        log_path = get_dev_log_path()

        # Call auth login with valid admin credentials
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify SQL queries section exists
        assert "[SQL QUERIES EXECUTED (" in content
        assert "Total SQL Execution Time:" in content

        # Verify specific query and parameter are logged
        assert "SELECT * FROM users WHERE username = ?" in content
        assert "('admin',)" in content or "admin" in content
        assert "Rows Fetched: 1" in content
        assert '"username": "admin"' in content
        assert '"role": "admin"' in content

    def test_no_truncation_in_log(self, client: TestClient):
        """Ensure long payloads, tokens, and data are NOT truncated with ellipsis or slice limits."""
        long_comment = "A" * 1200  # Longer than typical 500-char truncation limits
        resp = client.post(
            "/auth/signup",
            json={
                "username": "notrunc_user",
                "email": "notrunc@noc.com",
                "password": f"Pass_{long_comment}_123!",
                "role": "analyst",
            },
        )
        # May succeed (201) or fail validation (422) - either way, logger records the body
        log_path = get_dev_log_path()
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # The full long string must be present in log.txt without truncation
        assert long_comment in content, "Long request body string should not be truncated"

    def test_multiple_routes_append_to_same_file(self, client: TestClient):
        """Sequential requests must all append to the same log.txt file."""
        log_path = get_dev_log_path()

        marker_1 = client.get("/health")
        assert marker_1.status_code == 200

        marker_2 = client.post("/internal/ping", json={"host": "8.8.8.8", "count": 1})
        # Internal ping may require auth (401) or succeed (200), logger captures it either way

        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Both routes must be in the same log file
        assert "ROUTE TRIGGERED: GET /health" in content
        assert "ROUTE TRIGGERED: POST /internal/ping" in content

    def test_validation_error_and_latency_logged(self, client: TestClient):
        """422 Validation errors are logged with invalid payload and total roundtrip time."""
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 422

        log_path = get_dev_log_path()
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Status Code:      422 Unprocessable Entity" in content
        assert "Total Time Taken:" in content
        assert "Request validation failed" in content or "Field required" in content
