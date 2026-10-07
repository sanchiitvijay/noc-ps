"""
Tests for internal diagnostics (ping, traceroute, nslookup).

Because FAKE_DIAGNOSTICS=True is set in conftest, these run the mocked
responses instantly without touching the network.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestInternalDiagnostics:
    def test_ping_success(self, client: TestClient, admin_headers: dict):
        resp = client.post(
            "/internal/ping",
            json={"host": "google.com", "count": 4},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["host"] == "google.com"
        assert data["reachable"] is True
        assert data["packet_loss_pct"] == 0.0

    def test_ping_unreachable_private_ip(self, client: TestClient, admin_headers: dict):
        # 10.x.x.x IPs are mocked to fail in fake diagnostics mode
        resp = client.post(
            "/internal/ping",
            json={"host": "10.0.0.5"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["reachable"] is False
        assert data["packet_loss_pct"] == 100.0

    def test_traceroute_success(self, client: TestClient, admin_headers: dict):
        resp = client.post(
            "/internal/traceroute",
            json={"host": "example.com"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "hops" in data
        assert isinstance(data["hops"], list)
        assert len(data["hops"]) > 0

    def test_nslookup_success(self, client: TestClient, admin_headers: dict):
        resp = client.post(
            "/internal/nslookup",
            json={"host": "example.com"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "addresses" in data
        assert isinstance(data["addresses"], list)

    def test_internal_routes_require_auth(self, client: TestClient):
        # unauthenticated requests should 401
        resp = client.post("/internal/ping", json={"host": "example.com"})
        assert resp.status_code == 401

        resp = client.post("/internal/traceroute", json={"host": "example.com"})
        assert resp.status_code == 401

        resp = client.post("/internal/nslookup", json={"host": "example.com"})
        assert resp.status_code == 401
