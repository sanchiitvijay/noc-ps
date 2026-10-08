"""
Tests for /solution-summaries CRUD endpoints.

Also validates the delete_summary freshness-filter fix: a summary older
than the configured cache TTL (simulated by updating its updated_at directly) must still
be deletable via the API.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient
from config import settings


_VALID_BODY = {
    "event_id": 999_001,
    "hypothesis": "Test root cause hypothesis",
    "recommended_steps": ["Step 1: Check logs", "Step 2: Restart service"],
    "confidence": "medium",
    "generated_by": "analyst",
}


class TestSolutionSummariesList:
    def test_list_summaries_authenticated(self, client: TestClient, admin_headers: dict):
        """GET /solution-summaries returns 200 with a list."""
        resp = client.get("/solution-summaries", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)

    def test_list_summaries_unauthenticated(self, client: TestClient):
        resp = client.get("/solution-summaries")
        assert resp.status_code == 401

    def test_list_summaries_filter_by_event_id(self, client: TestClient, admin_headers: dict):
        """Filter by event_id is accepted without error."""
        resp = client.get(
            "/solution-summaries",
            params={"event_id": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 200


class TestSolutionSummariesGet:
    def test_get_summary_not_found(self, client: TestClient, admin_headers: dict):
        """Fetching a non-existent summary returns 404."""
        resp = client.get("/solution-summaries/999_999_001", headers=admin_headers)
        assert resp.status_code == 404

    def test_get_summary_unauthenticated(self, client: TestClient):
        resp = client.get("/solution-summaries/1")
        assert resp.status_code == 401

    def test_get_expired_summary_returns_not_found(
        self,
        client: TestClient,
        admin_headers: dict,
    ):
        event_id = 999_990
        created = client.post(
            "/solution-summaries",
            json={**_VALID_BODY, "event_id": event_id},
            headers=admin_headers,
        )
        assert created.status_code == 200

        with sqlite3.connect(settings.db_path) as conn:
            conn.execute(
                """UPDATE ticket_solution_summaries
                   SET updated_at = datetime('now', ?)
                   WHERE event_id = ?""",
                (f"-{settings.SOLUTION_SUMMARY_CACHE_TTL_MINUTES + 1} minutes", event_id),
            )

        response = client.get(f"/solution-summaries/{event_id}", headers=admin_headers)
        assert response.status_code == 404


class TestSolutionSummariesPost:
    def test_create_summary_success(self, client: TestClient, admin_headers: dict):
        """POST creates a new summary and returns it."""
        resp = client.post(
            "/solution-summaries",
            json=_VALID_BODY,
            headers=admin_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["event_id"] == _VALID_BODY["event_id"]
        assert data["hypothesis"] == _VALID_BODY["hypothesis"]
        assert data["recommended_steps"] == _VALID_BODY["recommended_steps"]

    def test_create_summary_missing_required_field(self, client: TestClient, admin_headers: dict):
        """Missing required field returns 400."""
        resp = client.post(
            "/solution-summaries",
            json={"event_id": 999_002, "hypothesis": "Missing steps"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_create_summary_invalid_confidence(self, client: TestClient, admin_headers: dict):
        """Invalid confidence value returns 400."""
        resp = client.post(
            "/solution-summaries",
            json={**_VALID_BODY, "event_id": 999_003, "confidence": "ultra"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_create_summary_invalid_steps_type(self, client: TestClient, admin_headers: dict):
        """recommended_steps must be a list; a string returns 400."""
        resp = client.post(
            "/solution-summaries",
            json={**_VALID_BODY, "event_id": 999_004, "recommended_steps": "do something"},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_upsert_updates_existing(self, client: TestClient, admin_headers: dict):
        """POSTing twice to the same event_id updates the existing record."""
        event_id = 999_005
        client.post(
            "/solution-summaries",
            json={**_VALID_BODY, "event_id": event_id, "hypothesis": "original"},
            headers=admin_headers,
        )
        resp = client.post(
            "/solution-summaries",
            json={**_VALID_BODY, "event_id": event_id, "hypothesis": "updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["hypothesis"] == "updated"

    def test_create_summary_unauthenticated(self, client: TestClient):
        resp = client.post("/solution-summaries", json=_VALID_BODY)
        assert resp.status_code == 401

    def test_create_summary_analyst_allowed(self, client: TestClient, analyst_headers: dict):
        """Analyst role can create summaries (analyst_or_admin route)."""
        resp = client.post(
            "/solution-summaries",
            json={**_VALID_BODY, "event_id": 999_010},
            headers=analyst_headers,
        )
        assert resp.status_code == 200


class TestSolutionSummariesDelete:
    def test_delete_summary_success(self, client: TestClient, admin_headers: dict):
        """Create then delete a summary; delete returns 200."""
        event_id = 999_020
        create_resp = client.post(
            "/solution-summaries",
            json={**_VALID_BODY, "event_id": event_id},
            headers=admin_headers,
        )
        assert create_resp.status_code == 200

        del_resp = client.delete(f"/solution-summaries/{event_id}", headers=admin_headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["success"] is True

    def test_delete_summary_not_found(self, client: TestClient, admin_headers: dict):
        """Deleting a non-existent summary returns 404."""
        resp = client.delete("/solution-summaries/999_999_002", headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_summary_unauthenticated(self, client: TestClient):
        resp = client.delete("/solution-summaries/1")
        assert resp.status_code == 401
