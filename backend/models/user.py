"""
User model — mirrors the ``users`` table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    """Representation of a row in the ``users`` table.

    Attributes:
        id: Auto-incremented primary key.
        username: Unique login name.
        email: Unique email address.
        hashed_password: bcrypt hash of the user's password.
        role: Either ``'admin'`` or ``'analyst'``.
        is_active: Whether the account is active (1) or disabled (0).
        created_at: Timestamp of account creation.
    """

    id: int
    username: str
    email: str
    hashed_password: str
    role: str
    is_active: int
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict) -> "User":
        """Construct a User from a database row dict."""
        return cls(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            hashed_password=row["hashed_password"],
            role=row["role"],
            is_active=row["is_active"],
            created_at=row.get("created_at"),
        )
