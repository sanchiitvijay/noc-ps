"""
Security utilities — JWT creation/validation and password hashing.

Uses:
- PyJWT (``import jwt``) for token operations — available in the environment
- ``hashlib.pbkdf2_hmac`` + ``secrets`` for password hashing — pure stdlib,
  no external dependencies required

All cryptographic operations are centralized here so they can be
easily audited and updated without touching business logic.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt, JWTError

from config import settings

logger = logging.getLogger(__name__)

# PBKDF2 parameters for password hashing
_PBKDF2_ITERATIONS = 390_000  # OWASP 2023 minimum recommendation
_PBKDF2_HASH = "sha256"
_SALT_BYTES = 32


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plain-text password using PBKDF2-HMAC-SHA256.

    The output format is ``pbkdf2:sha256:<iterations>$<salt_hex>$<hash_hex>``
    so that the hash is self-describing and the parameters can be changed
    without invalidating existing hashes.

    Args:
        plain: The raw password string supplied by the user.

    Returns:
        A self-describing hash string safe to store in the database.
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH,
        plain.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    salt_hex = salt.hex()
    hash_hex = dk.hex()
    return f"pbkdf2:{_PBKDF2_HASH}:{_PBKDF2_ITERATIONS}${salt_hex}${hash_hex}"


def verify_password(plain: str, stored: str) -> bool:
    """Verify a plain-text password against a stored PBKDF2 hash.

    Uses ``hmac.compare_digest`` for constant-time comparison to prevent
    timing attacks.

    Args:
        plain: The raw password string supplied by the user.
        stored: The stored hash string (from ``hash_password``).

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        # Format: pbkdf2:<hash_name>:<iterations>$<salt_hex>$<hash_hex>
        algo_part, rest = stored.split("$", 2)[0], stored.split("$", 1)[1]
        # algo_part = "pbkdf2:sha256:390000"
        parts = algo_part.split(":")
        hash_name = parts[1]
        iterations = int(parts[2])
        salt_hex, expected_hex = rest.split("$", 1)

        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac(
            hash_name,
            plain.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT utilities (PyJWT)
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    """Return the current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str | int,
    role: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The ``sub`` claim — typically the user's integer ID as a string.
        role: The user's role, embedded as the ``role`` claim.
        extra_claims: Optional dict of additional claims to embed.

    Returns:
        A signed JWT string.
    """
    now = _utcnow()
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),  # unique token ID for blocklist support
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str | int) -> str:
    """Create a signed JWT refresh token.

    Refresh tokens have a longer lifetime and carry a ``"type": "refresh"``
    claim to distinguish them from access tokens.

    Args:
        subject: The ``sub`` claim — typically the user's integer ID.

    Returns:
        A signed JWT string.
    """
    now = _utcnow()
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token.

    Args:
        token: The raw JWT string (without ``"Bearer "`` prefix).

    Returns:
        The decoded payload dict.

    Raises:
        jwt.exceptions.InvalidTokenError: If the token is invalid, expired,
            or tampered with.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )


def get_token_jti(token: str) -> str | None:
    """Extract the ``jti`` claim from a token without raising on error.

    Args:
        token: Raw JWT string.

    Returns:
        The ``jti`` string, or None if decoding fails.
    """
    try:
        payload = decode_token(token)
        return payload.get("jti")
    except JWTError:
        return None
