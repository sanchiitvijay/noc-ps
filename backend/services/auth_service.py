"""
Authentication service — user CRUD and token management.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

from database.connection import execute_write, fetch_all, fetch_one
from utils.exceptions import AuthenticationError, ConflictError, NotFoundError
from utils.security import (
    create_access_token,
    create_refresh_token,
    get_token_jti,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


async def create_user(
    conn: aiosqlite.Connection,
    username: str,
    email: str,
    password: str,
    role: str = "analyst",
) -> dict:
    """Insert a new user record and return the created user dict.

    Args:
        conn: Active database connection.
        username: Desired username (must be unique).
        email: Email address (must be unique).
        password: Plain-text password to hash and store.
        role: User role — ``'admin'`` or ``'analyst'``.

    Returns:
        Dict representation of the newly created user row.

    Raises:
        ConflictError: If the username or email already exists.
    """
    # Check for existing username
    existing = await fetch_one(
        conn,
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (username, email),
    )
    if existing:
        raise ConflictError("A user with that username or email already exists")

    hashed = hash_password(password)
    user_id = await execute_write(
        conn,
        """
        INSERT INTO users (username, email, hashed_password, role, is_active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (username, email, hashed, role),
    )
    user = await fetch_one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        raise RuntimeError("Failed to retrieve newly created user")
    return user


async def get_user_by_username(
    conn: aiosqlite.Connection,
    username: str,
) -> dict | None:
    """Fetch a user row by username.

    Args:
        conn: Active database connection.
        username: The username to look up.

    Returns:
        User row dict, or None if not found.
    """
    return await fetch_one(
        conn, "SELECT * FROM users WHERE username = ?", (username,)
    )


async def get_user_by_id(
    conn: aiosqlite.Connection,
    user_id: int,
) -> dict | None:
    """Fetch a user row by primary key.

    Args:
        conn: Active database connection.
        user_id: The user's primary key.

    Returns:
        User row dict, or None if not found.
    """
    return await fetch_one(conn, "SELECT * FROM users WHERE id = ?", (user_id,))


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def authenticate_user(
    conn: aiosqlite.Connection,
    username: str,
    password: str,
) -> dict:
    """Validate credentials and return the user dict.

    Args:
        conn: Active database connection.
        username: Supplied username.
        password: Supplied plain-text password.

    Returns:
        The user row dict on successful authentication.

    Raises:
        AuthenticationError: If credentials are invalid or account inactive.
    """
    user = await get_user_by_username(conn, username)
    if not user:
        raise AuthenticationError("Invalid username or password")
    if not user["is_active"]:
        raise AuthenticationError("Account is disabled")
    if not verify_password(password, user["hashed_password"]):
        raise AuthenticationError("Invalid username or password")
    return user


def build_token_pair(user: dict) -> dict:
    """Generate an access + refresh token pair for a user.

    Args:
        user: User row dict from the database.

    Returns:
        Dict with ``access_token``, ``refresh_token``, ``token_type``,
        ``expires_in`` keys.
    """
    from config import settings  # local import to avoid circular dependency

    access = create_access_token(subject=user["id"], role=user["role"])
    refresh = create_refresh_token(subject=user["id"])
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ---------------------------------------------------------------------------
# Token blocklist
# ---------------------------------------------------------------------------


async def add_token_to_blocklist(
    conn: aiosqlite.Connection,
    token: str,
    expires_at: datetime,
) -> None:
    """Add a JWT to the blocklist so it can no longer be used.

    Args:
        conn: Active database connection.
        token: The raw JWT string.
        expires_at: The token's expiry datetime (used for future cleanup).
    """
    jti = get_token_jti(token)
    if not jti:
        logger.warning("Could not extract JTI from token for blocklisting")
        return
    try:
        await execute_write(
            conn,
            """
            INSERT OR IGNORE INTO token_blocklist (jti, expires_at)
            VALUES (?, ?)
            """,
            (jti, expires_at.isoformat()),
        )
    except Exception as exc:
        logger.error("Failed to add token to blocklist: %s", exc)


async def is_token_blocked(conn: aiosqlite.Connection, jti: str) -> bool:
    """Check whether a JTI has been blocklisted (logged-out token).

    Args:
        conn: Active database connection.
        jti: The ``jti`` claim from the JWT payload.

    Returns:
        True if the token is blocked, False otherwise.
    """
    row = await fetch_one(
        conn, "SELECT id FROM token_blocklist WHERE jti = ?", (jti,)
    )
    return row is not None
