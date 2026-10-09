"""
NOC Automation Backend — FastAPI application entrypoint.

Startup sequence:
  1. Run database migrations (CREATE TABLE IF NOT EXISTS)
  2. Create default admin user if no users exist
  3. Register middleware (CORS, activity logger)
  4. Mount all routers
  5. Register exception handlers

Usage::

    cd backend/
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database.migrations import create_default_admin, run_migrations
from middleware.activity_logger import ActivityLoggerMiddleware
from middleware.dev_logger import DevLoggingMiddleware
from routers import admin, auth, error_info, internal, logs, metrics, simulation, solution_summaries
from utils.exceptions import register_exception_handlers

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle events.

    On startup:
        - Runs DB migrations (idempotent)
        - Creates the default admin user if users table is empty

    On shutdown:
        - Any cleanup (currently a no-op)
    """
    logger.info("=== NOC Automation Backend starting up ===")
    logger.info("Database: %s", settings.db_path)
    logger.info("FAKE_DIAGNOSTICS: %s", settings.FAKE_DIAGNOSTICS)
    logger.info("GEMINI_API_KEY configured: %s", bool(settings.GEMINI_API_KEY))

    await run_migrations()
    await create_default_admin()

    logger.info("Startup complete — ready to serve requests")
    yield

    logger.info("=== NOC Automation Backend shutting down ===")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured FastAPI instance.
    """
    app = FastAPI(
        title="NOC Automation API",
        description=(
            "Backend API for the Network Operations Center (NOC) automation system. "
            "Provides metrics, event log queries, diagnostic tools, ticket history, "
            "and AI-powered error analysis."
        ),
        version="1.0.0",
        contact={
            "name": "NOC Engineering Team",
            "email": "noc-engineering@example.com",
        },
        license_info={"name": "Proprietary"},
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["localhost", "http://localhost:3000", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Activity logger (must be added AFTER CORS so CORS headers are set first)
    app.add_middleware(ActivityLoggerMiddleware)

    # ── Dev logger (records route, latency, and all SQL queries/data to log.txt)
    if settings.DEV_LOG_ENABLED:
        app.add_middleware(DevLoggingMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(metrics.router)
    app.include_router(logs.router)
    app.include_router(admin.router)
    app.include_router(internal.router)
    app.include_router(error_info.router)
    app.include_router(solution_summaries.router)
    app.include_router(simulation.router)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="Health check")
    async def health_check():
        """Return a simple health indicator for load balancer / uptime monitoring."""
        return {"status": "ok", "version": "1.0.0"}

    return app


# ---------------------------------------------------------------------------
# Module-level app instance (used by uvicorn)
# ---------------------------------------------------------------------------

app = create_app()
