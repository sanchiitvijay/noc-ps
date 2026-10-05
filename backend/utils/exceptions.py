"""
Custom exception classes and FastAPI exception handlers.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Custom exception classes
# ---------------------------------------------------------------------------


class NOCException(Exception):
    """Base exception for all application-specific errors.

    Attributes:
        message: Human-readable description of the error.
        status_code: HTTP status code to return.
    """

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(NOCException):
    """Raised when a requested resource cannot be found (404)."""

    def __init__(self, resource: str = "Resource", identifier: str = "") -> None:
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(detail, status_code=status.HTTP_404_NOT_FOUND)


class AuthenticationError(NOCException):
    """Raised for invalid credentials or missing auth tokens (401)."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(NOCException):
    """Raised when the user lacks permission for an action (403)."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, status_code=status.HTTP_403_FORBIDDEN)


class ValidationError(NOCException):
    """Raised for business-logic validation failures (422)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class ConflictError(NOCException):
    """Raised when a resource already exists (409)."""

    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, status_code=status.HTTP_409_CONFLICT)


class FileTooLargeError(NOCException):
    """Raised when an uploaded file exceeds the size limit (413)."""

    def __init__(self, max_mb: int) -> None:
        super().__init__(
            f"File exceeds maximum allowed size of {max_mb} MB",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


# ---------------------------------------------------------------------------
# Standard API error response builder
# ---------------------------------------------------------------------------


def error_response(
    message: str,
    status_code: int,
    details: dict | None = None,
) -> JSONResponse:
    """Build a consistent JSON error response body.

    All error responses follow the shape::

        {"success": false, "message": "...", "data": null, "details": {...}}

    Args:
        message: Human-readable error description.
        status_code: HTTP status code.
        details: Optional dict with additional diagnostic information.

    Returns:
        A FastAPI JSONResponse.
    """
    body = {
        "success": False,
        "message": message,
        "data": None,
        "details": details or {},
    }
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------


from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI application.

    Args:
        app: The FastAPI application instance.
    """

    @app.exception_handler(NOCException)
    async def noc_exception_handler(request: Request, exc: NOCException) -> JSONResponse:
        """Handle all NOCException subclasses uniformly."""
        return error_response(exc.message, exc.status_code)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle generic 404 HTTP errors (route not found)."""
        return error_response(
            f"Endpoint '{request.url.path}' does not exist",
            status.HTTP_404_NOT_FOUND,
        )

    @app.exception_handler(405)
    async def method_not_allowed_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle 405 Method Not Allowed errors."""
        return error_response(
            f"Method '{request.method}' not allowed on '{request.url.path}'",
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle FastAPI body/query validation errors."""
        errors = exc.errors()
        details = {"validation_errors": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in errors]}
        return error_response(
            "Request validation failed",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle standard Starlette/FastAPI HTTPExceptions."""
        return error_response(str(exc.detail), exc.status_code)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle any unhandled exceptions to prevent leaking tracebacks."""
        logger.error("Unhandled Exception: %s", exc, exc_info=True)
        return error_response(
            "An unexpected internal server error occurred",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
