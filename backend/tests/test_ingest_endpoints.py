"""
End-to-end tests for CSV ingestion and simulation endpoints via the API.
"""

from __future__ import annotations

from pathlib import Path
import time

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAKE_EVENTS_CSV = FIXTURES / "fake_events.csv"
FAKE_TICKETS_CSV = FIXTURES / "fake_tickets.csv"


def _wait_for_job(client: TestClient, job_id: int, admin_headers: dict, timeout: float = 10.0) -> dict:
    start = time.time()
    while time.time() - start < timeout:
        resp = client.get(f"/admin/ingest-excel/{job_id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(0.1)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


class TestIngestApiEndpoints:
    def test_upload_events_via_ingest_excel_endpoint(self, client: TestClient, admin_headers: dict):
        """Upload events CSV via /admin/ingest-excel and verify background processing completes."""
        events_bytes = FAKE_EVENTS_CSV.read_bytes()
        resp = client.post(
            "/admin/ingest-excel",
            headers=admin_headers,
            files={"file": ("fake_events.csv", events_bytes, "text/csv")},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["success"] is True
        job_id = body["data"]["id"]

        job_data = _wait_for_job(client, job_id, admin_headers)
        assert job_data["status"] == "completed"
        assert job_data["rows_processed"] == 12
        assert job_data["error_message"] is None

    def test_upload_tickets_via_ingest_excel_endpoint(self, client: TestClient, admin_headers: dict):
        """Upload tickets CSV via /admin/ingest-excel and verify background processing completes."""
        tickets_bytes = FAKE_TICKETS_CSV.read_bytes()
        resp = client.post(
            "/admin/ingest-excel",
            headers=admin_headers,
            files={"file": ("fake_tickets.csv", tickets_bytes, "text/csv")},
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["success"] is True
        job_id = body["data"]["id"]

        job_data = _wait_for_job(client, job_id, admin_headers)
        assert job_data["status"] == "completed"
        assert job_data["rows_processed"] == 7
        assert job_data["error_message"] is None

    def test_upload_via_typed_endpoints(self, client: TestClient, admin_headers: dict):
        """Upload via /admin/ingest/error-csv and /admin/ingest/ticket-csv."""
        events_bytes = FAKE_EVENTS_CSV.read_bytes()
        resp = client.post(
            "/admin/ingest/error-csv",
            headers=admin_headers,
            files={"file": ("events.csv", events_bytes, "text/csv")},
        )
        assert resp.status_code == 202
        job_id = resp.json()["data"]["id"]
        job_data = _wait_for_job(client, job_id, admin_headers)
        assert job_data["status"] == "completed"
        assert job_data["rows_processed"] == 12

        tickets_bytes = FAKE_TICKETS_CSV.read_bytes()
        resp = client.post(
            "/admin/ingest/ticket-csv",
            headers=admin_headers,
            files={"file": ("tickets.csv", tickets_bytes, "text/csv")},
        )
        assert resp.status_code == 202
        job_id = resp.json()["data"]["id"]
        job_data = _wait_for_job(client, job_id, admin_headers)
        assert job_data["status"] == "completed"
        assert job_data["rows_processed"] == 7


class TestSimulationAndErrorInfoWorkflow:
    def test_simulated_live_logs_have_event_type_id_and_valid_records(
        self, client: TestClient, admin_headers: dict
    ):
        """Live logs from /simulate/logs include event_type_id and valid records for /error-info."""
        resp = client.get(
            "/simulate/logs",
            params={"count": 10, "synthetic_ratio": 0.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        logs = resp.json()["data"]
        assert len(logs) > 0

        for log in logs:
            assert "event_id" in log
            assert "event_type_id" in log
            assert log["event_type_id"] is not None
            assert log["device_id"] is not None

            # Verify that calling /error-info for this sampled live event works
            error_info_resp = client.get(
                "/error-info",
                params={"event_id": log["event_id"]},
                headers=admin_headers,
            )
            assert error_info_resp.status_code == 200, (
                f"Failed for event_id {log['event_id']}: {error_info_resp.text}"
            )
            error_info = error_info_resp.json()["data"]
            assert error_info["device"] is not None
            assert error_info["event_type"] is not None
