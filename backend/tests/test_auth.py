"""
Tests for the /auth/* endpoints.

Covers: signup, login, /me, logout, token validation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success(self, client: TestClient):
        """Admin login returns 200 with tokens."""
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "access_token" in data["data"]["tokens"]
        assert "refresh_token" in data["data"]["tokens"]

    def test_login_wrong_password(self, client: TestClient):
        """Wrong password returns 401."""
        resp = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401
        assert resp.json()["success"] is False

    def test_login_missing_fields(self, client: TestClient):
        """Missing username/password returns 422."""
        resp = client.post("/auth/login", json={})
        assert resp.status_code == 422

    def test_login_unknown_user(self, client: TestClient):
        """Unknown user returns 401."""
        resp = client.post("/auth/login", json={"username": "ghost", "password": "ghost"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/signup
# ---------------------------------------------------------------------------


class TestSignup:
    def test_signup_success(self, client: TestClient):
        """New user signup returns 201."""
        resp = client.post(
            "/auth/signup",
            json={
                "username": "pytest_user",
                "email": "pytest@noc.com",
                "password": "SecurePass1!",
                "role": "analyst",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["user"]["username"] == "pytest_user"
        assert "access_token" in body["data"]["tokens"]

    def test_signup_duplicate_username(self, client: TestClient):
        """Duplicate username returns 409."""
        resp = client.post(
            "/auth/signup",
            json={
                "username": "pytest_user",
                "email": "another@noc.com",
                "password": "SecurePass1!",
            },
        )
        assert resp.status_code == 409

    def test_signup_invalid_email(self, client: TestClient):
        """Invalid email returns 422."""
        resp = client.post(
            "/auth/signup",
            json={"username": "newuser2", "email": "not-an-email", "password": "SecurePass1!"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


class TestMe:
    def test_me_authenticated(self, client: TestClient, admin_headers: dict):
        """Authenticated /me returns user profile."""
        resp = client.get("/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["username"] == "admin"

    def test_me_unauthenticated(self, client: TestClient):
        """Unauthenticated /me returns 401."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        """Invalid token returns 401."""
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# /auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_success(self, client: TestClient):
        """Logout with a valid token returns 200."""
        # Get a fresh token
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        token = resp.json()["data"]["tokens"]["access_token"]
        logout_resp = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert logout_resp.status_code == 200
        assert logout_resp.json()["success"] is True
