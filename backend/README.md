# NOC Automation Backend API

This repository contains the FastAPI backend for the Network Operations Center (NOC) automation system. It provides an intelligent network alert analysis platform that integrates event logs, ServiceNow ticket history, automated preliminary diagnostic checks, and an LLM-powered solution engine.

## Features

- **JWT Authentication:** Secure API access with role-based restrictions (admin/analyst).
- **Network Event Diagnostics:** Interfaces to query large volumes of historical device events and logs.
- **ServiceNow Ticket History Matching:** Matches a given event against historic ServiceNow tickets based on device ID, IPs, site codes, and names using multi-strategy confidence grading.
- **Diagnostics Simulation Engine:** Configurable module (`FAKE_DIAGNOSTICS`) to simulate `ping`, `traceroute`, and `nslookup` (or run them via the system/remote API if enabled).
- **Gemini LLM Integration:** Synthesizes diagnostic info and past tickets into an actionable hypothesis and step-by-step resolution plan using `gemini-1.5-flash`.
- **Background Async Worker:** Ingests and normalizes large CSV/Excel ticket and event reports into the database without blocking the main event loop.
- **Activity Logging:** Middleware captures user footprints and actions to an activity log table automatically.

## Requirements

- Python 3.10+
- SQLite (aiosqlite)
- A Gemini API Key (Optional but required for LLM solutions. Will fallback to rule-based analysis if absent).

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
   # Edit .env and set GEMINI_API_KEY
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
| `DATABASE_URL` | SQLite connection string. | `sqlite:///./noc-automation2.db` |
| `SECRET_KEY` | Key for signing JWTs. | `change-me-in-production...` |
| `ALGORITHM` | JWT signing algorithm. | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token lifetime. | `30` |
| `GEMINI_API_KEY` | Google Gemini API key for the `/error-info` solution engine. | `""` |
| `FAKE_DIAGNOSTICS` | If `True`, mocks `ping`, `traceroute`, and `nslookup`. | `True` |
| `CORS_ORIGINS` | Allowed CORS origins. | `["*"]` |
| `MAX_INGEST_FILE_SIZE_MB` | File size limit for CSV data ingestion. | `100` |

## Data Ingestion Worker

The API provides an endpoint `/admin/ingest-excel` for administrators to upload new dumps of event logs or tickets (CSV/Excel format). This endpoint securely receives the payload and dispatches processing to an asyncio background worker inside `workers/ingest_worker.py`. 

To ingest data, authenticate as an admin, use the ingest endpoint, and track the state in the `ingest_jobs` table.

## API Documentation

For the comprehensive frontend API integration guide, please see [FRONTEND_API_DOC.md](FRONTEND_API_DOC.md).

For interactive OpenAPI docs, navigate to:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
