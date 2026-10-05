"""
Shared FastAPI dependencies for authentication and authorization.

Provides reusable ``Depends()`` callables that validate JWT tokens and
enforce role-based access control on protected routes.
"""

from __future__ import annotations

import logging
from typing import Annotated

import aiosqlite
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database.connection import AsyncConnection, get_connection
from jwt.exceptions import InvalidTokenError

from services.auth_service import get_user_by_id, is_token_blocked
from utils.security import decode_token

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
    conn: aiosqlite.Connection = Depends(get_connection),
) -> dict:
    """Validate the Bearer JWT token and return the authenticated user dict.

    Sets ``request.state.user`` so the activity logger middleware can pick
    up the user_id without re-decoding the token.

    Args:
        request: The current HTTP request (used to set state).
        credentials: Bearer token extracted from the Authorization header.
        conn: Database connection for blocklist and user lookup.

    Returns:
        The authenticated user row dict.

    Raises:
        HTTPException 401: If no token is provided, the token is invalid,
            expired, or has been blocklisted.
        HTTPException 403: If the user account is inactive.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type — must be an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required",
        )

    # Check blocklist
    jti = payload.get("jti", "")
    if jti and await is_token_blocked(conn, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    user_id = int(payload.get("sub", 0))
    user = await get_user_by_id(conn, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Store user in request state for middleware
    request.state.user = dict(user)
    return dict(user)


def require_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Dependency that enforces the ``admin`` role.

    Args:
        current_user: Authenticated user dict from ``get_current_user``.

    Returns:
        The current user dict if the role check passes.

    Raises:
        HTTPException 403: If the user is not an admin.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def require_analyst_or_admin(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> dict:
    """Dependency that enforces the ``admin`` or ``analyst`` role.

    Args:
        current_user: Authenticated user dict from ``get_current_user``.

    Returns:
        The current user dict if the role check passes.

    Raises:
        HTTPException 403: If the user has an unrecognized role.
    """
    if current_user.get("role") not in ("admin", "analyst"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst or Admin role required",
        )
    return current_user
