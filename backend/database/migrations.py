"""
Database migrations module.

Creates all application-managed tables that don't exist in the original
NOC database schema (users, activity_logs, ingest_jobs).

Called once at application startup via the FastAPI lifespan handler.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL Statements
# ---------------------------------------------------------------------------

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT    NOT NULL UNIQUE,
    email           TEXT    NOT NULL UNIQUE,
    hashed_password TEXT    NOT NULL,
    role            TEXT    NOT NULL DEFAULT 'analyst'
                    CHECK(role IN ('admin', 'analyst')),
    is_active       INTEGER NOT NULL DEFAULT 1,   -- 0=inactive, 1=active (SQLite bool)
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_USERS_IDX = """
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
"""

CREATE_ACTIVITY_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS activity_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER,                       -- NULL for unauthenticated requests
    action          TEXT    NOT NULL,              -- e.g. "POST /auth/login"
    endpoint        TEXT    NOT NULL,
    ip_address      TEXT,
    request_body    TEXT,                          -- JSON blob, passwords sanitized
    response_status INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
"""

CREATE_ACTIVITY_LOGS_IDX_USER = """
CREATE INDEX IF NOT EXISTS idx_activity_user_id  ON activity_logs(user_id);
"""

CREATE_ACTIVITY_LOGS_IDX_TIME = """
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at);
"""

CREATE_INGEST_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    started_at      DATETIME,
    completed_at    DATETIME,
    rows_processed  INTEGER DEFAULT 0,
    error_message   TEXT,
    triggered_by    INTEGER,                       -- user_id of uploader

    FOREIGN KEY (triggered_by) REFERENCES users(id) ON DELETE SET NULL
);
"""

CREATE_INGEST_JOBS_IDX = """
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_status ON ingest_jobs(status);
"""

# ---------------------------------------------------------------------------
# Token blocklist (for logout invalidation)
# ---------------------------------------------------------------------------

CREATE_TOKEN_BLOCKLIST_TABLE = """
CREATE TABLE IF NOT EXISTS token_blocklist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    jti         TEXT NOT NULL UNIQUE,  -- JWT ID claim
    expires_at  DATETIME NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_TOKEN_BLOCKLIST_IDX = """
CREATE INDEX IF NOT EXISTS idx_token_blocklist_jti ON token_blocklist(jti);
"""

# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------

ALL_MIGRATIONS: list[tuple[str, str]] = [
    ("users table", CREATE_USERS_TABLE),
    ("users index", CREATE_USERS_IDX),
    ("activity_logs table", CREATE_ACTIVITY_LOGS_TABLE),
    ("activity_logs user_id index", CREATE_ACTIVITY_LOGS_IDX_USER),
    ("activity_logs created index", CREATE_ACTIVITY_LOGS_IDX_TIME),
    ("ingest_jobs table", CREATE_INGEST_JOBS_TABLE),
    ("ingest_jobs status index", CREATE_INGEST_JOBS_IDX),
    ("token_blocklist table", CREATE_TOKEN_BLOCKLIST_TABLE),
    ("token_blocklist jti index", CREATE_TOKEN_BLOCKLIST_IDX),
]


async def run_migrations() -> None:
    """Run all CREATE TABLE IF NOT EXISTS migrations.

    Safe to call on every startup — idempotent by design.
    Logs each migration step for observability.
    """
    logger.info("Running database migrations …")

    def _do_migrations():
        conn = sqlite3.connect(settings.db_path)
        conn.execute("PRAGMA foreign_keys=ON;")
        for name, ddl in ALL_MIGRATIONS:
            try:
                conn.execute(ddl)
                logger.debug("Migration OK: %s", name)
            except Exception as exc:
                conn.close()
                logger.error("Migration FAILED [%s]: %s", name, exc)
                raise
        conn.commit()
        conn.close()

    await asyncio.to_thread(_do_migrations)
    logger.info("All migrations completed successfully.")


async def create_default_admin() -> None:
    """Insert the default admin user if no users exist yet.

    Uses the ADMIN_USERNAME and ADMIN_PASSWORD from settings.
    The password is hashed with bcrypt before storage.
    """
    # Import here to avoid circular imports at module level
    from utils.security import hash_password  # noqa: PLC0415

    def _do_create():
        conn = sqlite3.connect(settings.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")

        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        count = row["cnt"] if row else 0

        if count == 0:
            hashed = hash_password(settings.ADMIN_PASSWORD)
            conn.execute(
                """
                INSERT INTO users (username, email, hashed_password, role, is_active)
                VALUES (?, ?, ?, 'admin', 1)
                """,
                (
                    settings.ADMIN_USERNAME,
                    f"{settings.ADMIN_USERNAME}@noc.local",
                    hashed,
                ),
            )
            conn.commit()
            conn.close()
            return True
        conn.close()
        return False

    created = await asyncio.to_thread(_do_create)
    if created:
        logger.info("Default admin user '%s' created.", settings.ADMIN_USERNAME)
    else:
        logger.debug("Users table already populated — skipping default admin creation.")

