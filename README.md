# NOC Automation & Performance Platform

An automated Network Operations Center (NOC) metrics, alert monitoring, and root-cause analysis platform. Built with FastAPI (Python) on the backend and React + Vite + Tailwind CSS on the frontend.

## Quick Start

### Prerequisites
- Python 3.10+ (Python 3.14 compatible)
- Node.js 18+ & npm

### Starting the Application

The startup scripts automatically create the Python virtual environment (`.venv`), install pip packages, install frontend `node_modules`, and launch both backend and frontend servers together.

#### Linux / macOS
```bash
./start.sh
```
Press `Ctrl+C` in the terminal to stop both servers cleanly.

#### Windows
**Command Prompt:**
```cmd
start.bat
```

**PowerShell:**
```powershell
.\start.ps1
```
Press `Ctrl+C` or close the terminal window to stop.

Once started:
- **Frontend**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Directory Layout

```
noc-ps/
├── backend/                  # FastAPI application, database connections, routers, and services
│   ├── database/             # SQLite connection wrapper, migrations, and schema definitions
│   ├── routers/              # API endpoint routes (sites, metrics, tickets, logs, etc.)
│   ├── services/             # Core business logic and query engines
│   └── tests/                # Pytest automated test suite
├── frontend/                 # React (Vite, Tailwind CSS, Lucide icons, Recharts)
│   └── src/pages/            # UI pages (Dashboard, Sites, Alerts, Tickets, Logs, etc.)
├── data/                     # Data assets
│   ├── raw/                  # Anonymized source dataset CSVs
│   ├── samples/              # Sample CSVs for upload testing
│   └── legacy_dbs/           # Inactive historical SQLite database snapshots
├── docs/                     # Architecture diagrams, specifications, schemas, and notes
├── scripts/                  # Standalone benchmarks, query performance testers, updater tools
├── sql/                      # Migration SQL scripts, query templates, and table seed dumps
├── noc_database_setup 1/     # Initial database ETL setup scripts
├── noc_automation_4.db       # Active SQLite database file
└── start.sh / start.bat / start.ps1   # Multi-platform unified start scripts
```

---

## Running Tests

### Backend Tests
```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/
```

### Frontend Build Verification
```bash
cd frontend
npm run build
```
