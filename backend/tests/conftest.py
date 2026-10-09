"""
pytest configuration for the NOC Automation backend tests.

Sets up a FastAPI TestClient using a temporary copy of the active database
(noc_automation_4.db), runs all migrations on it, and provides reusable
fixtures for authenticated admin and analyst users.

The copy is made once per session and discarded afterwards, so the live
database is never modified.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Resolve the active DB path
# ---------------------------------------------------------------------------

# The backend's default DATABASE_URL points to noc_automation_4.db in the
# project root.  We locate it relative to this file so the tests work from
# any working directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIVE_DB = _REPO_ROOT / "noc_automation_4.db"
# Fallback: noc-automation2.db (older copy kept for compatibility)
_FALLBACK_DB = _REPO_ROOT / "noc-automation2.db"


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory) -> str:
    """Create a temporary SQLite database file by copying the active one.

    Falls back to noc-automation2.db if the primary DB is absent.
    """
    db_dir = tmp_path_factory.mktemp("testdb")
    target = db_dir / "test_noc.db"
    source = _LIVE_DB if _LIVE_DB.exists() else _FALLBACK_DB
    shutil.copy2(source, target)
    return str(target)


@pytest.fixture(scope="session", autouse=True)
def patch_settings(tmp_db_path: str):
    """Patch settings to use the temp DB and disable external services."""
    from config import settings  # noqa: PLC0415

    settings.DATABASE_URL = f"sqlite:///{tmp_db_path}"
    settings.GEMINI_API_KEY = ""   # disable real LLM calls in tests
    settings.GROQ_API_KEY   = ""   # disable real LLM calls in tests
    settings.FAKE_DIAGNOSTICS = True
    settings.SECRET_KEY = "test-secret-key-for-pytest-only"
    settings.DEV_LOG_ENABLED = True
    settings.DEV_LOG_FILE = str(Path(tmp_db_path).with_name("test-dev-log.txt"))
    yield


@pytest.fixture(scope="session")
def app(patch_settings):
    """Create the FastAPI app after settings are patched."""
    from main import create_app  # noqa: PLC0415

    return create_app()


@pytest.fixture(scope="session")
def client(app) -> Generator:
    """Synchronous TestClient for simple, non-async tests."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _get_token(client: TestClient, username: str, password: str) -> str:
    """Log in and return the access token."""
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["data"]["tokens"]["access_token"]


@pytest.fixture(scope="session")
def admin_token(client: TestClient) -> str:
    """Return a valid admin JWT access token."""
    return _get_token(client, "admin", "admin123")


@pytest.fixture(scope="session")
def admin_headers(admin_token: str) -> dict:
    """Return auth headers for the admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def analyst_token(client: TestClient) -> str:
    """Return a valid analyst JWT access token (creates user if needed)."""
    # Try to log in first; create user if that fails.
    try:
        return _get_token(client, "pytest_analyst", "AnalystPass1!")
    except AssertionError:
        resp = client.post(
            "/auth/signup",
            json={
                "username": "pytest_analyst",
                "email": "pytest_analyst@example.com",
                "password": "AnalystPass1!",
                "role": "analyst",
            },
        )
        assert resp.status_code in (200, 201), f"Analyst signup failed: {resp.text}"
        return resp.json()["data"]["tokens"]["access_token"]


@pytest.fixture(scope="session")
def analyst_headers(analyst_token: str) -> dict:
    """Return auth headers for the analyst user."""
    return {"Authorization": f"Bearer {analyst_token}"}
