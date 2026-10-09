# NOC Automation Backend API

This repository contains the FastAPI backend for the Network Operations Center (NOC) automation system. It provides an intelligent network alert analysis platform that integrates event logs, ServiceNow ticket history, automated preliminary diagnostic checks, and an LLM-powered solution engine.

## Features

- **JWT Authentication:** Secure API access with role-based restrictions (admin/analyst).
- **Network Event Diagnostics:** Interfaces to query large volumes of historical device events and logs.
- **ServiceNow Ticket History Matching:** Matches a given event against historic ServiceNow tickets based on device ID, IPs, site codes, and names using multi-strategy confidence grading.
- **Diagnostics Simulation Engine:** Configurable module (`FAKE_DIAGNOSTICS`) to simulate `ping`, `traceroute`, and `nslookup` (or run them via the system/remote API if enabled).
- **AI Suggestions:** Tries Gemini first, Groq (`openai/gpt-oss-20b`) as fallback, then built-in rule-based guidance.
- **Background Async Worker:** Accepts CSV/XLS/XLSX event and ticket exports, auto-detects their headers, and reports import-job status.
- **Activity Logging:** Middleware records user actions; frequent ingest-job status polls are excluded to avoid noisy writes during large imports.

## Requirements

- Python 3.10+
- SQLite (aiosqlite)
- Gemini and/or Groq API keys are optional; rule-based guidance is used when both providers are unavailable.

## Setup & Installation

1. **Clone & Virtual Environment**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   Copy `.env.example` to `.env` and configure your settings:
   ```bash
   cp .env.example .env
   # Set GEMINI_API_KEY and/or GROQ_API_KEY in .env
   ```

4. **Run the Application**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   *Note: On first startup, database migrations are automatically run and a default admin user (`admin` / `admin123`) is created if no users exist.*

## Configuration Reference

Settings can be customized via the `.env` file (processed by `pydantic-settings`).

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `DATABASE_URL` | SQLite connection string. | Set in `backend/.env`; otherwise uses the project-local configured database |
| `SECRET_KEY` | Key for signing JWTs. | `change-me-in-production...` |
| `ALGORITHM` | JWT signing algorithm. | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token lifetime. | `30` |
| `GEMINI_API_KEY` | Optional primary provider for `/error-info`. | Configure in `.env` |
| `GROQ_API_KEY` | Optional fallback provider for `/error-info`. | Configure in `.env` |
| `SOLUTION_SUMMARY_CACHE_TTL_MINUTES` | Freshness lifetime for cached Gemini/Groq summaries. | `10` |
| `FAKE_DIAGNOSTICS` | If `True`, mocks `ping`, `traceroute`, and `nslookup`. | `True` |
| `CORS_ORIGINS` | Allowed CORS origins. | `["*"]` |
| `MAX_INGEST_FILE_SIZE_MB` | File size limit for CSV data ingestion. | `100` |

## Data Ingestion Worker

The API provides `/admin/ingest-excel` for administrators to upload event or ticket exports (`.csv`, `.xls`, or `.xlsx`). It auto-detects the file type from supported headers, returns `202 Accepted` with an ingest-job ID, and processes the upload in an asyncio task in `workers/ingest_worker.py`. The frontend polls `/admin/ingest-excel/{job_id}` until the job reaches `completed` or `failed`.

The worker accepts both the repository's source export columns and normalized API columns. The task is in-process, not durable: an API restart can interrupt an active import. Large supplied event exports take around two minutes on the local development setup.

## API Documentation

For the comprehensive frontend API integration guide, please see [FRONTEND_API_DOC.md](FRONTEND_API_DOC.md).

For interactive OpenAPI docs, navigate to:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
