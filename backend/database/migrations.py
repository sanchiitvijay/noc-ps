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
    user_agent      TEXT,                          -- captured by the activity logger
    duration_ms     REAL,                          -- handler latency
    target_resource TEXT,                          -- resource parsed from the path
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

# Columns added after the original activity_logs schema shipped.
_ACTIVITY_LOG_COLUMNS: tuple[tuple[str, str], ...] = (
    ("user_agent", "TEXT"),
    ("duration_ms", "REAL"),
    ("target_resource", "TEXT"),
)

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
# Ticket solution summaries (pre-computed per event)
# ---------------------------------------------------------------------------

CREATE_TICKET_SOLUTION_SUMMARIES_TABLE = """
CREATE TABLE IF NOT EXISTS ticket_solution_summaries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        INTEGER NOT NULL,
    hypothesis      TEXT    NOT NULL,
    recommended_steps TEXT  NOT NULL,   -- JSON array stored as text
    confidence      TEXT    NOT NULL DEFAULT 'medium'
                    CHECK(confidence IN ('high', 'medium', 'low')),
    generated_by    TEXT    NOT NULL DEFAULT 'rule-based',
    source_tickets  TEXT,               -- JSON array of ticket numbers used
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(event_id)
);
"""

CREATE_TSS_IDX = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_tss_event
ON ticket_solution_summaries(event_id);
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


def _migrate_activity_log_columns(conn: sqlite3.Connection) -> None:
    """Add activity_logs columns that post-date the original schema.

    ``CREATE TABLE IF NOT EXISTS`` never alters an existing table, so databases
    created before these columns shipped would otherwise reject every INSERT
    issued by ``create_activity_log()`` — silently losing all audit records.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(activity_logs)")}
    for name, ddl_type in _ACTIVITY_LOG_COLUMNS:
        if name not in columns:
            conn.execute(f"ALTER TABLE activity_logs ADD COLUMN {name} {ddl_type}")
            logger.debug("Added activity_logs.%s column", name)


def _migrate_ticket_solution_summaries(conn: sqlite3.Connection) -> None:
    """Upgrade event-type summaries while preserving the original table."""
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("ticket_solution_summaries",),
    ).fetchone()
    if not table:
        conn.execute(CREATE_TICKET_SOLUTION_SUMMARIES_TABLE)
    else:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(ticket_solution_summaries)")
        }
        if "event_id" not in columns:
            if "event_type_id" not in columns:
                raise RuntimeError(
                    "ticket_solution_summaries has an unsupported schema"
                )

            legacy_name = "ticket_solution_summaries_legacy"
            suffix = 1
            while conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (legacy_name,),
            ).fetchone():
                suffix += 1
                legacy_name = f"ticket_solution_summaries_legacy_{suffix}"

            conn.execute(
                f"ALTER TABLE ticket_solution_summaries RENAME TO {legacy_name}"
            )
            conn.execute(CREATE_TICKET_SOLUTION_SUMMARIES_TABLE)
            conn.execute(
                f"""
                INSERT INTO ticket_solution_summaries
                    (event_id, hypothesis, recommended_steps, confidence,
                     generated_by, source_tickets, created_at, updated_at)
                SELECT (
                    SELECT MIN(event_id) FROM event_logs
                    WHERE event_type_id = legacy.event_type_id
                ), legacy.hypothesis, legacy.recommended_steps,
                   legacy.confidence, legacy.generated_by, legacy.source_tickets,
                   legacy.created_at, legacy.updated_at
                FROM {legacy_name} AS legacy
                WHERE EXISTS (
                    SELECT 1 FROM event_logs
                    WHERE event_type_id = legacy.event_type_id
                )
                """
            )

    conn.execute(CREATE_TSS_IDX)


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
        try:
            _migrate_activity_log_columns(conn)
            logger.debug("Migration OK: activity_logs extended columns")
        except Exception as exc:
            conn.close()
            logger.error("Migration FAILED [activity_logs columns]: %s", exc)
            raise
        try:
            _migrate_ticket_solution_summaries(conn)
            logger.debug("Migration OK: ticket_solution_summaries event key")
        except Exception as exc:
            conn.close()
            logger.error("Migration FAILED [ticket_solution_summaries]: %s", exc)
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

