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
from datetime import datetime
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from fastapi import HTTPException
from config import settings
from utils.exceptions import NOCException

try:
    from middleware.dev_logger import record_sql_query
except ImportError:
    def record_sql_query(record: dict) -> None:
        pass

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
        start_time = time.perf_counter()

        def _run():
            cur = self._conn.execute(query, params)
            return cur

        try:
            cursor = await asyncio.to_thread(_run)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            clean_q = query.strip().upper()
            is_select = clean_q.startswith(("SELECT", "PRAGMA", "EXPLAIN", "WITH"))

            query_record = {
                "query": query,
                "params": params,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(),
                "rowcount": getattr(cursor, "rowcount", -1),
                "lastrowid": getattr(cursor, "lastrowid", None),
                "is_select": is_select,
                "rows": [],
                "fetched": False,
                "error": None,
            }
            record_sql_query(query_record)
            return AsyncCursor(cursor, self._conn, query_record)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            query_record = {
                "query": query,
                "params": params,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(),
                "rowcount": -1,
                "lastrowid": None,
                "is_select": False,
                "rows": [],
                "fetched": False,
                "error": str(exc),
            }
            record_sql_query(query_record)
            raise

    async def executemany(self, query: str, params_list: list[tuple]) -> None:
        """Execute a statement against multiple parameter sets.

        Args:
            query: SQL string with ``?`` placeholders.
            params_list: List of parameter tuples.
        """
        start_time = time.perf_counter()
        try:
            await asyncio.to_thread(self._conn.executemany, query, params_list)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            query_record = {
                "query": query,
                "params": params_list,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(),
                "batch_count": len(params_list),
                "rowcount": getattr(self._conn, "total_changes", -1),
                "lastrowid": None,
                "is_select": False,
                "rows": [],
                "fetched": False,
                "error": None,
            }
            record_sql_query(query_record)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            query_record = {
                "query": query,
                "params": params_list,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(),
                "batch_count": len(params_list),
                "rowcount": -1,
                "lastrowid": None,
                "is_select": False,
                "rows": [],
                "fetched": False,
                "error": str(exc),
            }
            record_sql_query(query_record)
            raise

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

    Wraps a ``sqlite3.Cursor`` and exposes async ``fetchone``/``fetchall``/``fetchmany``
    methods, the ``lastrowid`` property, and the ``rowcount`` property.
    """

    def __init__(
        self,
        cursor: sqlite3.Cursor,
        conn: sqlite3.Connection,
        query_record: dict | None = None,
    ) -> None:
        self._cursor = cursor
        self._conn = conn
        self._query_record = query_record

    @property
    def lastrowid(self) -> int | None:
        """Return the rowid of the last inserted row."""
        return self._cursor.lastrowid

    @property
    def rowcount(self) -> int:
        """Return the number of affected rows."""
        return self._cursor.rowcount

    async def fetchone(self) -> dict | None:
        """Fetch and return the next row as a dict, or None."""
        row = await asyncio.to_thread(self._cursor.fetchone)
        if row is None:
            if self._query_record is not None:
                self._query_record["fetched"] = True
            return None
        # sqlite3.Row supports dict(row) when row_factory = sqlite3.Row
        dict_row = dict(row) if isinstance(row, sqlite3.Row) else row
        if self._query_record is not None:
            self._query_record["rows"].append(dict(dict_row) if isinstance(dict_row, dict) else dict_row)
            self._query_record["fetched"] = True
        return dict_row

    async def fetchall(self) -> list[dict]:
        """Fetch and return all remaining rows as a list of dicts."""
        rows = await asyncio.to_thread(self._cursor.fetchall)
        dict_rows = [
            dict(r) if isinstance(r, sqlite3.Row) else r
            for r in rows
        ]
        if self._query_record is not None:
            self._query_record["rows"].extend([
                dict(r) if isinstance(r, dict) else r
                for r in dict_rows
            ])
            self._query_record["fetched"] = True
        return dict_rows

    async def fetchmany(self, size: int = 1) -> list[dict]:
        """Fetch and return up to *size* rows as a list of dicts."""
        rows = await asyncio.to_thread(self._cursor.fetchmany, size)
        dict_rows = [
            dict(r) if isinstance(r, sqlite3.Row) else r
            for r in rows
        ]
        if self._query_record is not None:
            self._query_record["rows"].extend([
                dict(r) if isinstance(r, dict) else r
                for r in dict_rows
            ])
            self._query_record["fetched"] = True
        return dict_rows

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

