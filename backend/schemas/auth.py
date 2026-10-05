"""
Pydantic schemas for authentication endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    """Request body for POST /auth/signup.

    Attributes:
        username: Desired username (3–50 alphanumeric characters).
        email: Valid email address.
        password: Plain-text password (min 8 chars); stored as bcrypt hash.
        role: Account role — ``'admin'`` or ``'analyst'`` (default: analyst).
    """

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="analyst")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Ensure role is one of the allowed values."""
        if v not in ("admin", "analyst"):
            raise ValueError("role must be 'admin' or 'analyst'")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Ensure username contains only alphanumeric characters and underscores."""
        if not v.replace("_", "").isalnum():
            raise ValueError("username may only contain letters, digits, and underscores")
        return v.lower()


class LoginRequest(BaseModel):
    """Request body for POST /auth/login.

    Attributes:
        username: Registered username.
        password: Plain-text password.
    """

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    """Request body for POST /auth/logout.

    Attributes:
        refresh_token: The refresh token to invalidate.
    """

    refresh_token: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    """JWT token pair returned after successful login/signup.

    Attributes:
        access_token: Short-lived Bearer token for API calls.
        refresh_token: Long-lived token to obtain new access tokens.
        token_type: Always ``"bearer"``.
        expires_in: Seconds until the access token expires.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    """Public user profile returned in responses.

    Passwords and internal fields are excluded.
    """

    id: int
    username: str
    email: str
    role: str
    is_active: int
    created_at: str | None = None


class SignupResponse(BaseModel):
    """Response for POST /auth/signup."""

    user: UserResponse
    tokens: TokenResponse
