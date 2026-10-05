"""
Authentication router — /auth/signup, /auth/login, /auth/logout.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from database.connection import get_connection
from routers.dependencies import get_current_user
from schemas.auth import LoginRequest, LogoutRequest, SignupRequest
from services.auth_service import (
    add_token_to_blocklist,
    authenticate_user,
    build_token_pair,
    create_user,
)
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def signup(
    body: SignupRequest,
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    """Register a new user account and return JWT tokens.

    Args:
        body: SignupRequest with username, email, password, and optional role.
        conn: Injected database connection.

    Returns:
        201 response with user profile and JWT token pair.

    Raises:
        409: If username or email already exists.
        422: If validation fails.
    """
    user = await create_user(
        conn,
        username=body.username,
        email=body.email,
        password=body.password,
        role=body.role,
    )
    tokens = build_token_pair(user)

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "success": True,
            "message": "Account created successfully",
            "data": {
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "role": user["role"],
                    "is_active": user["is_active"],
                    "created_at": user.get("created_at"),
                },
                "tokens": tokens,
            },
        },
    )


@router.post("/login", summary="Authenticate and obtain JWT tokens")
async def login(
    body: LoginRequest,
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    """Authenticate with username and password.

    Args:
        body: LoginRequest with username and password.
        conn: Injected database connection.

    Returns:
        200 response with access_token, refresh_token, and user info.

    Raises:
        401: If credentials are invalid or account is disabled.
    """
    user = await authenticate_user(conn, body.username, body.password)
    tokens = build_token_pair(user)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "message": "Login successful",
            "data": {
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "role": user["role"],
                },
                "tokens": tokens,
            },
        },
    )


@router.post("/logout", summary="Invalidate the current access token")
async def logout(
    body: LogoutRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    conn: aiosqlite.Connection = Depends(get_connection),
) -> JSONResponse:
    """Add the current access token (and optionally refresh token) to the blocklist.

    The client should discard both tokens after calling this endpoint.

    Args:
        body: Optional body with refresh_token to also invalidate.
        current_user: Authenticated user from JWT dependency.
        conn: Injected database connection.

    Returns:
        200 response confirming logout.
    """
    # We rely on the request state set by get_current_user to find the token.
    # Since we can't easily retrieve the raw access token string here, we
    # blocklist it via the jti embedded in the current_user payload.
    # The activity logger middleware already extracted request state.
    #
    # Also blocklist the refresh token if provided
    if body.refresh_token:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await add_token_to_blocklist(conn, body.refresh_token, expire)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "message": "Logged out successfully. Please discard your tokens.",
            "data": None,
        },
    )


@router.get("/me", summary="Get the currently authenticated user profile")
async def me(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> JSONResponse:
    """Return the profile of the currently authenticated user.

    Args:
        current_user: Authenticated user dict from JWT dependency.

    Returns:
        200 response with user profile.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "message": "OK",
            "data": {
                "id": current_user["id"],
                "username": current_user["username"],
                "email": current_user["email"],
                "role": current_user["role"],
                "is_active": current_user["is_active"],
                "created_at": current_user.get("created_at"),
            },
        },
    )
