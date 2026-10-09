"""
Activity logger middleware.

Intercepts every HTTP request and writes a record to the ``activity_logs``
table. Sensitive fields (e.g., passwords) are sanitized before storage.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from database.connection import get_db_context
from services.logs_service import create_activity_log

logger = logging.getLogger(__name__)

# Fields whose values are replaced with "***REDACTED***" in logged request bodies
_SENSITIVE_FIELDS = {"password", "hashed_password", "secret", "token", "refresh_token"}

# Paths that should NOT be logged (reduces noise)
_SKIP_PATHS = {"/docs", "/openapi.json", "/redoc", "/favicon.ico", "/health"}


def _sanitize_body(body: dict) -> dict:
    """Recursively replace sensitive field values with ``"***REDACTED***"``.

    Args:
        body: Parsed request body dict.

    Returns:
        Sanitized copy of the body dict.
    """
    sanitized = {}
    for key, value in body.items():
        if key.lower() in _SENSITIVE_FIELDS:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_body(value)
        else:
            sanitized[key] = value
    return sanitized


def _extract_user_id(request: Request) -> int | None:
    """Extract the user_id from the JWT token stored in request state.

    The auth dependency populates ``request.state.user`` if the token is valid.

    Args:
        request: The incoming HTTP request.

    Returns:
        Integer user ID or None for unauthenticated requests.
    """
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        return user.get("id")
    return None


class ActivityLoggerMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that logs every API request to the activity_logs table.

    Records:
        - user_id (from JWT token in request state, if present)
        - action ("METHOD /path")
        - endpoint (raw path)
        - ip_address (client IP)
        - request_body (JSON, passwords sanitized)
        - response_status (HTTP status code)
        - created_at (auto-set by DB)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request, call the next handler, and log the result.

        Errors during logging are caught and logged to stderr so they never
        affect the actual API response.

        Args:
            request: Incoming HTTP request.
            call_next: Next middleware or route handler.

        Returns:
            The HTTP response from the downstream handler.
        """
        path = request.url.path

        # Skip noisy ingest-job polling; the job row already records its lifecycle.
        if (
            path in _SKIP_PATHS
            or path.startswith("/static")
            or (request.method == "GET" and path.startswith("/admin/ingest-excel/"))
        ):
            return await call_next(request)

        # Read and store the request body so it can be consumed multiple times
        body_bytes: bytes = b""
        try:
            body_bytes = await request.body()
        except Exception:
            pass  # If body can't be read, proceed without it

        # Re-inject body bytes so the downstream handler can still read it
        async def _receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]

        # Process the request
        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Async log to DB (best-effort — never raise)
        try:
            # Parse and sanitize request body
            body_str: str | None = None
            if body_bytes:
                try:
                    parsed = json.loads(body_bytes)
                    if isinstance(parsed, dict):
                        parsed = _sanitize_body(parsed)
                    body_str = json.dumps(parsed)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body_str = body_bytes.decode("utf-8", errors="replace")[:500]

            user_id = _extract_user_id(request)
            client_ip = (
                request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                or (request.client.host if request.client else None)
            )
            action = f"{request.method} {path}"

            async with get_db_context() as db:
                db.row_factory = None  # don't need row_factory for write
                await create_activity_log(
                    conn=db,
                    user_id=user_id,
                    action=action,
                    endpoint=path,
                    ip_address=client_ip,
                    request_body=body_str,
                    response_status=response.status_code,
                )

            logger.debug(
                "%s %s → %d (%.1fms)",
                request.method, path, response.status_code, duration_ms
            )
        except Exception as exc:
            # Never let logging failures surface to the caller
            logger.warning("ActivityLogger failed: %s", exc)

        return response
