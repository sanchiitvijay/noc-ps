# Network Alerts Automation Platform (NAAP)

React 19, JavaScript, Vite, Zustand, React Router, and Recharts.

## Run the frontend

```sh
npm install
npm run dev
```

During local development, Vite proxies API requests to `http://localhost:8000`. Set `VITE_API_BASE_URL` to use another backend; a URL ending in `/health` is normalized to the API root. Production builds call the configured backend directly.

## Run with the NOC backend

The backend and SQLite database are in `backend +database`. Start the API in one PowerShell window:

```powershell
cd ".\backend +database\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///C:/Users/ABK3292/Downloads/frontend code is/frontend repo/backend +database/noc_automation_4.db"
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a second window, start the frontend from `frontend repo` with `npm run dev`. The frontend login and dashboard requests will then use the local API and database. The backend creates its default admin account on first startup if the database has no users; otherwise, use an account already stored in that database. Interactive API docs are available at `http://localhost:8000/docs`.

## Demo login

Use either offline account:

- **Admin:** `admin` / `admin123` — dashboard, alerts, automation, data upload, and activity logs.
- **Analyst:** `analyst@networkops.com` / `User@123` — dashboard, alert logs, diagnostics, and AI recommendations.

Offline demo accounts use local sample data and do not require the backend. The header marks offline demo mode.

When using another account with the API available, credentials are sent to `/auth/login` normally.
