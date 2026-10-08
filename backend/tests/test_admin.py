"""
Tests for /admin/* endpoints: activity-log, ingest-excel, ingest status.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import io

from fastapi.testclient import TestClient


# Minimal valid event CSV matching the worker's column fingerprint
_EVENT_CSV = (
    "event_type_name,device_name,message,event_time\n"
    "Node Down,test-device-01,Link is down,2024-01-01 00:00:00\n"
).encode()

# Minimal valid ticket CSV matching the worker's column fingerprint
_TICKET_CSV = (
    "ticket_number,short_description,state,created_on\n"
    "INC9999999,Test ticket,Open,2024-01-01\n"
).encode()


class TestActivityLog:
    def test_list_activity_log_admin(self, client: TestClient, admin_headers: dict):
        """Admin can list activity logs — returns 200 with data + meta."""
        resp = client.get("/admin/activity-log", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "data" in body
        assert isinstance(body["data"], list)
        assert "meta" in body

    def test_list_activity_log_unauthenticated(self, client: TestClient):
        """Unauthenticated request returns 401."""
        resp = client.get("/admin/activity-log")
        assert resp.status_code == 401

    def test_list_activity_log_analyst_rejected(self, client: TestClient, analyst_headers: dict):
        """Analyst role is rejected (admin-only endpoint)."""
        resp = client.get("/admin/activity-log", headers=analyst_headers)
        assert resp.status_code == 403

    def test_list_activity_log_pagination(self, client: TestClient, admin_headers: dict):
        """Pagination parameters are accepted."""
        resp = client.get(
            "/admin/activity-log",
            params={"page": 1, "page_size": 10},
            headers=admin_headers,
        )
        assert resp.status_code == 200


class TestIngestExcel:
    """Tests for POST /admin/ingest-excel (the auto-detect alias)."""

    def test_ingest_status_poll_skips_activity_write(
        self,
        client: TestClient,
        admin_headers: dict,
        monkeypatch,
    ):
        import middleware.activity_logger as activity_logger

        activity_log_attempts = []

        @asynccontextmanager
        async def observe_activity_connection():
            activity_log_attempts.append(True)
            yield None

        monkeypatch.setattr(
            activity_logger,
            "get_db_context",
            observe_activity_connection,
        )

        response = client.get(
            "/admin/ingest-excel/999999",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert activity_log_attempts == []

    def test_ingest_event_csv_returns_202(self, client: TestClient, admin_headers: dict):
        """Uploading a valid event CSV returns 202 with a job_id."""
        resp = client.post(
            "/admin/ingest-excel",
            headers=admin_headers,
            files={"file": ("events.csv", io.BytesIO(_EVENT_CSV), "text/csv")},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["success"] is True
        assert "id" in body["data"]
        assert body["data"]["id"] is not None

    def test_ingest_ticket_csv_returns_202(self, client: TestClient, admin_headers: dict):
        """Uploading a valid ticket CSV returns 202 with a job_id."""
        resp = client.post(
            "/admin/ingest-excel",
            headers=admin_headers,
            files={"file": ("tickets.csv", io.BytesIO(_TICKET_CSV), "text/csv")},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["success"] is True
        assert "id" in body["data"]

    def test_ingest_unsupported_type_returns_400(self, client: TestClient, admin_headers: dict):
        """Uploading an unsupported file type returns 400."""
        resp = client.post(
            "/admin/ingest-excel",
            headers=admin_headers,
            files={"file": ("data.json", io.BytesIO(b'{"x":1}'), "application/json")},
        )
        assert resp.status_code == 400

    def test_ingest_unauthenticated_returns_401(self, client: TestClient):
        """Unauthenticated upload returns 401."""
        resp = client.post(
            "/admin/ingest-excel",
            files={"file": ("events.csv", io.BytesIO(_EVENT_CSV), "text/csv")},
        )
        assert resp.status_code == 401

    def test_ingest_analyst_rejected_returns_403(self, client: TestClient, analyst_headers: dict):
        """Analyst cannot upload files (admin-only)."""
        resp = client.post(
            "/admin/ingest-excel",
            headers=analyst_headers,
            files={"file": ("events.csv", io.BytesIO(_EVENT_CSV), "text/csv")},
        )
        assert resp.status_code == 403

    def test_ingest_status_after_upload(self, client: TestClient, admin_headers: dict):
        """After uploading, job status can be retrieved via /admin/ingest-excel/{job_id}."""
        # Upload
        upload_resp = client.post(
            "/admin/ingest-excel",
            headers=admin_headers,
            files={"file": ("events.csv", io.BytesIO(_EVENT_CSV), "text/csv")},
        )
        assert upload_resp.status_code == 202
        job_id = upload_resp.json()["data"]["id"]

        # Poll status
        status_resp = client.get(
            f"/admin/ingest-excel/{job_id}",
            headers=admin_headers,
        )
        assert status_resp.status_code == 200
        status_body = status_resp.json()
        assert status_body["success"] is True
        assert status_body["data"]["id"] == job_id
        assert status_body["data"]["status"] in ("pending", "running", "completed", "failed")


class TestIngestSpecificEndpoints:
    """Tests for the typed ingest endpoints."""

    def test_ingest_error_csv_returns_202(self, client: TestClient, admin_headers: dict):
        resp = client.post(
            "/admin/ingest/error-csv",
            headers=admin_headers,
            files={"file": ("events.csv", io.BytesIO(_EVENT_CSV), "text/csv")},
        )
        assert resp.status_code == 202

    def test_ingest_ticket_csv_returns_202(self, client: TestClient, admin_headers: dict):
        resp = client.post(
            "/admin/ingest/ticket-csv",
            headers=admin_headers,
            files={"file": ("tickets.csv", io.BytesIO(_TICKET_CSV), "text/csv")},
        )
        assert resp.status_code == 202
