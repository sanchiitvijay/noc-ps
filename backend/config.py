"""
Application configuration using pydantic-settings.

All settings are read from environment variables or a .env file.
Never hardcode secrets — always use this module.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables / .env file.

    Attributes:
        DATABASE_URL: Path to the SQLite database file.
        SECRET_KEY: Secret key used to sign JWT tokens.
        ALGORITHM: JWT signing algorithm.
        ACCESS_TOKEN_EXPIRE_MINUTES: Lifetime of access tokens in minutes.
        REFRESH_TOKEN_EXPIRE_DAYS: Lifetime of refresh tokens in days.
        GEMINI_API_KEY: Google Gemini API key for LLM features.
        SOLUTION_SUMMARY_CACHE_TTL_MINUTES: Freshness window for saved solution summaries.
        FAKE_DIAGNOSTICS: If True, ping/traceroute/nslookup return mocked results.
        REAL_DIAGNOSTIC_ENDPOINT: Optional remote endpoint for real diagnostics.
        CORS_ORIGINS: List of allowed CORS origins.
        LOG_LEVEL: Python logging level string.
        MAX_INGEST_FILE_SIZE_MB: Maximum allowed file size for CSV/Excel uploads.
        ADMIN_USERNAME: Default admin username created on first startup.
        ADMIN_PASSWORD: Default admin password created on first startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = f"sqlite:///{Path(__file__).resolve().parents[1] / 'noc_automation_4.db'}"

    # ── JWT / Auth ────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── LLM / Gemini ──────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = "AQ.Ab8RN6Jx254gPcMElEsUaNyHTWSjCiuBFzUvkbIji0rGFfbNNA"

    # ── LLM / Groq fallback ───────────────────────────────────────────────────
    GROQ_API_KEY: str = ""  # Set to enable Groq as Gemini fallback (llama-3.3-70b-versatile)

    SOLUTION_SUMMARY_CACHE_TTL_MINUTES: int = Field(default=10, gt=0, le=1440)

    # ── Diagnostics ───────────────────────────────────────────────────────────
    FAKE_DIAGNOSTICS: bool = True
    REAL_DIAGNOSTIC_ENDPOINT: str = ""  # Optional remote endpoint (URL)

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["*"]

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    DEV_LOG_ENABLED: bool = False
    DEV_LOG_FILE: str = "log.txt"

    # ── Ingest ────────────────────────────────────────────────────────────────
    MAX_INGEST_FILE_SIZE_MB: int = 100

    # ── Default Admin ─────────────────────────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is a valid Python logging level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}")
        return upper

    @property
    def db_path(self) -> str:
        """Extract the filesystem path from DATABASE_URL.

        Strips the ``sqlite:///`` prefix so aiosqlite can open the file.
        """
        return self.DATABASE_URL.replace("sqlite:///", "")

    @property
    def max_ingest_bytes(self) -> int:
        """Convert MAX_INGEST_FILE_SIZE_MB to bytes."""
        return self.MAX_INGEST_FILE_SIZE_MB * 1024 * 1024


# Module-level singleton — import this everywhere
settings = Settings()
