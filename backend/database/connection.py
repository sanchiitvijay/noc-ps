"""
Database connection module.

Provides async SQLite access using the stdlib ``sqlite3`` module wrapped
in ``asyncio.to_thread`` for non-blocking operation. This approach avoids
the ``aiosqlite`` dependency while maintaining a clean async interface.

A thin ``AsyncConnection`` wrapper is used so that the rest of the codebase
can call ``await conn.execute(...)`` with the same syntax it would use with
aiosqlite.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from fastapi import HTTPException
from config import settings
from utils.exceptions import NOCException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thin async wrapper around sqlite3.Connection
# ---------------------------------------------------------------------------


class AsyncConnection:
    """Thin async wrapper around a synchronous ``sqlite3.Connection``.

    Runs all blocking DB calls in a thread pool via ``asyncio.to_thread``
    so they never block the event loop.

    This class intentionally mirrors a subset of the aiosqlite API so that
    service and router code can be written in a uniform async style.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ── Core execute helpers ─────────────────────────────────────────────────

    async def execute(self, query: str, params: tuple = ()) -> "AsyncCursor":
        """Execute a SQL statement and return an ``AsyncCursor``.

        Args:
            query: SQL string with ``?`` placeholders.
            params: Positional parameters for the query.

        Returns:
            An ``AsyncCursor`` wrapping the result.
        """
        def _run():
            cur = self._conn.execute(query, params)
            return cur

        cursor = await asyncio.to_thread(_run)
        return AsyncCursor(cursor, self._conn)

    async def executemany(self, query: str, params_list: list[tuple]) -> None:
        """Execute a statement against multiple parameter sets.

        Args:
            query: SQL string with ``?`` placeholders.
            params_list: List of parameter tuples.
        """
        await asyncio.to_thread(self._conn.executemany, query, params_list)

    async def commit(self) -> None:
        """Commit the current transaction."""
        await asyncio.to_thread(self._conn.commit)

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await asyncio.to_thread(self._conn.rollback)

    async def close(self) -> None:
        """Close the underlying connection."""
        await asyncio.to_thread(self._conn.close)

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._conn.row_factory = value


class AsyncCursor:
    """Async cursor returned by ``AsyncConnection.execute``.

    Wraps a ``sqlite3.Cursor`` and exposes async ``fetchone``/``fetchall``
    methods and the ``lastrowid`` property.
    """

    def __init__(self, cursor: sqlite3.Cursor, conn: sqlite3.Connection) -> None:
        self._cursor = cursor
        self._conn = conn

    @property
    def lastrowid(self) -> int | None:
        """Return the rowid of the last inserted row."""
        return self._cursor.lastrowid

    async def fetchone(self) -> dict | None:
        """Fetch and return the next row as a dict, or None."""
        row = await asyncio.to_thread(self._cursor.fetchone)
        if row is None:
            return None
        # sqlite3.Row supports dict(row) when row_factory = sqlite3.Row
        return dict(row)

    async def fetchall(self) -> list[dict]:
        """Fetch and return all remaining rows as a list of dicts."""
        rows = await asyncio.to_thread(self._cursor.fetchall)
        return [dict(r) for r in rows]

    # Context manager so callers can write:
    #   async with conn.execute(...) as cur:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


# ---------------------------------------------------------------------------
# Connection factory helpers
# ---------------------------------------------------------------------------


def _open_sqlite(path: str) -> sqlite3.Connection:
    """Open a sqlite3 connection with sensible defaults.

    Args:
        path: Filesystem path to the SQLite database file.

    Returns:
        An open ``sqlite3.Connection``.
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


async def get_connection() -> AsyncGenerator[AsyncConnection, None]:
    """FastAPI dependency that yields an async-wrapped SQLite connection.

    Yields:
        AsyncConnection: An async-compatible database connection.

    Example::

        async def my_endpoint(db: AsyncConnection = Depends(get_connection)):
            async with await db.execute("SELECT 1") as cur:
                row = await cur.fetchone()
    """
    raw_conn = await asyncio.to_thread(_open_sqlite, settings.db_path)
    conn = AsyncConnection(raw_conn)
    try:
        yield conn
    except (NOCException, HTTPException):
        # Business logic exception - just rollback, don't log as DB error
        await conn.rollback()
        raise
    except Exception as exc:
        logger.error("Database error: %s", exc, exc_info=True)
        await conn.rollback()
        raise
    finally:
        await conn.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncConnection, None]:
    """Async context manager version of ``get_connection``.

    Use this in background tasks where FastAPI ``Depends`` is unavailable.

    Example::

        async with get_db_context() as db:
            await fetch_one(db, "SELECT 1")
    """
    raw_conn = await asyncio.to_thread(_open_sqlite, settings.db_path)
    conn = AsyncConnection(raw_conn)
    try:
        yield conn
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Convenience query helpers
# ---------------------------------------------------------------------------


async def fetch_one(
    conn: AsyncConnection,
    query: str,
    params: tuple = (),
) -> dict | None:
    """Execute *query* and return the first row as a dict, or None.

    Args:
        conn: An active AsyncConnection.
        query: SQL query string with ``?`` placeholders.
        params: Tuple of parameters for the query.

    Returns:
        A dict mapping column names to values, or None if no row found.
    """
    async with await conn.execute(query, params) as cur:
        return await cur.fetchone()


async def fetch_all(
    conn: AsyncConnection,
    query: str,
    params: tuple = (),
) -> list[dict]:
    """Execute *query* and return all rows as a list of dicts.

    Args:
        conn: An active AsyncConnection.
        query: SQL query string with ``?`` placeholders.
        params: Tuple of parameters for the query.

    Returns:
        List of dicts, one per row.
    """
    async with await conn.execute(query, params) as cur:
        return await cur.fetchall()


async def execute_write(
    conn: AsyncConnection,
    query: str,
    params: tuple = (),
) -> int:
    """Execute a write statement, commit, and return the last row id.

    Args:
        conn: An active AsyncConnection.
        query: INSERT/UPDATE/DELETE SQL with ``?`` placeholders.
        params: Tuple of parameters.

    Returns:
        The ``lastrowid`` of the executed statement.
    """
    async with await conn.execute(query, params) as cur:
        last_id = cur.lastrowid
    await conn.commit()
    return last_id

