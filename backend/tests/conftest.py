"""
pytest configuration for the NOC Automation backend tests.

Sets up a FastAPI TestClient using an in-memory SQLite database,
creates all migrations, and provides reusable fixtures for authenticated
admin and analyst users.
"""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Override settings BEFORE importing the app so the test DB is used
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def tmp_db_path(tmp_path_factory) -> str:
    """Create a temporary SQLite database file by copying the real one."""
    import shutil
    db_dir = tmp_path_factory.mktemp("testdb")
    target = db_dir / "test_noc.db"
    source = Path(__file__).parent.parent.parent / "noc-automation2.db"
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
