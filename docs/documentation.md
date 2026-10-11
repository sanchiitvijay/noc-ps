# Network Alerts Automation Platform (NAAP) — Technical Documentation & Architecture Specification

> **Audience:** NOC Leadership, NOC Analysts, Network Engineers, Systems Architects, and Technical Management.  
> **Status:** Operational Pilot & Production Architecture Reference  
> **Last Updated:** October 2026  

---

## 1. Executive Summary & Problem Statement

### The Problem in Enterprise Network Operations
In a modern enterprise Network Operations Center (NOC), Tier-1 and Tier-2 engineers face high alert volumes ("alert storms") across thousands of distributed network devices (core switches, edge routers, distribution points, and wireless controllers).

Key operational pain points include:
1. **Context Fragmentation:** An alert in monitoring tools (SolarWinds, Nagios, Zabbix) does not tell the analyst whether this device flapped yesterday, what the historical ticket notes in ServiceNow were, or what the topology looks like.
2. **Repetitive Triage:** Analysts perform identical manual triage steps: host ping checks, traceroutes, DNS lookups, and searching ticket history across separate systems.
3. **Escalation Overhead:** Incidents are frequently misrouted to specialized engineering teams without proper preliminary triage context.

### The NAAP Solution
The **Network Alerts Automation Platform (NAAP)** unifies alert investigation into an automated, single-pane triage workflow:
- Correlates incoming alerts directly with **ServiceNow incident ticket history** and physical **Site locations**.
- Automatically runs preliminary **reachability and routing diagnostics** (`ping`, `traceroute`, `nslookup`).
- Delivers **AI-synthesized root-cause hypotheses** (via Google Gemini with Groq and deterministic rule fallbacks).
- Organizes the entire infrastructure across **1,027 sites** and **6,586 managed devices** with interactive site drill-down drawers.

```
                    ┌────────────────────────┐
                    │ Network Alert Arrives  │
                    └───────────┬────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │         Unified Automated Triage Flow        │
         ├──────────────────────┬───────────────────────┤
         │  1. Device Context   │  6,586 Managed Nodes  │
         │  2. Site Topology    │  1,027 Sites & States │
         │  3. Historical Links │  ServiceNow Tickets   │
         │  4. Fast Diagnostic  │  Ping, Trace, DNS     │
         │  5. AI Hypothesis    │  Gemini / Rule Engine │
         └──────────────────────┴───────────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │ Fast Informed Decision │
                    │ (Mitigate / Escalate)  │
                    └────────────────────────┘
```

---

## 2. High-Level Architecture

The platform follows a decoupled, security-first three-tier architecture:

```mermaid
flowchart TB
    subgraph ClientLayer ["Client Layer (Presentation)"]
        UI["React 19 SPA (Vite + Tailwind CSS + Recharts)<br/>• Unified Dashboard • Sites Topology Drawer<br/>• Live Logs & Triage • Admin & Ingestion"]
    end

    subgraph APILayer ["Application & Orchestration Layer"]
        API["FastAPI REST Service (Python 3.14 / Uvicorn)<br/>• JWT Bearer Auth & Role Guards (Admin / Analyst)<br/>• Audit & Latency Logging Middleware<br/>• Automated Diagnostics Engine<br/>• AI Synthesis Engine (Gemini / Groq / Rules)<br/>• Background Async Ingestion Worker"]
    end

    subgraph DataLayer ["Data & Persistence Layer"]
        DB[("SQLite 3 Database (noc_automation_4.db)<br/>• 6,586 Devices • 134,412 Event Logs<br/>• 1,027 Sites • 456 ServiceNow Tickets<br/>• Normalized Mappings & Cached AI Solutions")]
        RawFiles["Data Lake & Raw Assets (data/)<br/>• Raw Event CSVs • SN Ticket Extracts"]
    end

    subgraph ExternalServices ["External Intelligence & Diagnostics"]
        Gemini["Google Gemini API (Primary LLM)"]
        Groq["Groq API (Backup LLM)"]
        OSDiag["Local Host Network Stack (Optional Live Checks)"]
    end

    UI -->|HTTPS / JWT Authenticated REST| API
    API -->|aiosqlite Async Connection Pool| DB
    API -.->|Context + Diag Prompt| Gemini
    API -.->|Fallback Prompt| Groq
    API -.->|ICMP / UDP / DNS Sockets| OSDiag
    RawFiles -.->|Background Ingestion| API
```

### Architectural Tenets
1. **No Direct Database Access:** The client interface never accesses persistence layers directly; every interaction is mediated by authenticated, validated FastAPI endpoints.
2. **Defensive Fault Isolation:** The failure of external APIs (such as Gemini or Groq) never crashes or stalls the user experience; deterministic, rule-based fallback engines guarantee uptime.
3. **Auditability:** Every mutation, diagnostic run, login, and data ingestion is logged to an immutable `activity_logs` table.

---

## 3. Database Schema & Data Models

The system is powered by SQLite (`noc_automation_4.db`), optimized with indexes for sub-millisecond query response across 134,000+ records.

```mermaid
erDiagram
    USERS {
        int id PK
        string username "Unique account handle"
        string email "User email address"
        string hashed_password "PBKDF2-HMAC-SHA256"
        string role "'admin' or 'analyst'"
        int is_active "1 = Active, 0 = Disabled"
        datetime created_at
    }

    SITES {
        string site_code PK "e.g., 'S-1027'"
        string site_name "City or Facility Name"
        string state "Geographic State"
    }

    DEVICES {
        int device_id PK
        string device_name "e.g., 'SW-ATL-01'"
        string ip_address "Management IP"
        string site_code FK "Links to SITES"
        string machine_type "Router, Switch, Firewall, AP"
    }

    EVENT_TYPE_LOOKUP {
        int event_type_id PK
        string event_type_name "e.g., 'BGP Session Flap'"
        string severity "P1 (Critical) to P4 (Low)"
        string category "Hardware, Interface, Routing, Environment"
    }

    EVENT_LOGS {
        int event_id PK
        int device_id FK "Links to DEVICES"
        int event_type_id FK "Links to EVENT_TYPE_LOOKUP"
        string event_time "Timestamp or time-of-day"
        string message "Raw syslog / monitoring payload"
    }

    SN_TICKETS {
        int ticket_id PK
        string ticket_number "e.g., 'INC0491820'"
        string state "Open, In Progress, Resolved, Closed"
        string priority "1 - Critical to 4 - Low"
        string short_description "Summary of incident"
        string close_notes "Resolution narrative"
    }

    DEVICE_TICKET_MAP {
        int id PK
        int device_id FK
        int ticket_id FK
        float confidence "Heuristic correlation score (0.0 - 1.0)"
    }

    TICKET_SOLUTION_SUMMARIES {
        int id PK
        int event_id FK "Unique per event"
        string model_used "gemini-1.5, groq-llama3, or rule-based"
        string hypothesis "Synthesized root cause"
        string recommended_actions "Ordered action steps"
        datetime created_at
    }

    ACTIVITY_LOGS {
        int id PK
        int user_id FK
        string action "HTTP method and route"
        string ip_address "Client IP"
        int status_code "HTTP Status"
        float latency_ms "Execution time in milliseconds"
        datetime created_at
    }

    SITES ||--o{ DEVICES : "houses"
    DEVICES ||--o{ EVENT_LOGS : "generates"
    EVENT_TYPE_LOOKUP ||--o{ EVENT_LOGS : "classifies"
    DEVICES ||--o{ DEVICE_TICKET_MAP : "mapped in"
    SN_TICKETS ||--o{ DEVICE_TICKET_MAP : "resolves"
    EVENT_LOGS ||--o| TICKET_SOLUTION_SUMMARIES : "receives advice"
    USERS ||--o{ ACTIVITY_LOGS : "triggers"
```

### Key Dataset Statistics (Baseline Database)
| Entity | Record Count | Description |
|---|---:|---|
| **Sites** | 1,027 | Normalized facility locations, states, and coordinates |
| **Devices** | 6,586 | Managed network devices across all enterprise facilities |
| **Event Logs** | 134,412 | Historical and simulated monitoring alerts and telemetry |
| **Event Types** | 91 | Unique catalog of network event categories and severities |
| **ServiceNow Tickets** | 456 | Historical enterprise tickets with root-cause resolutions |
| **Device-Ticket Links** | 2,314 | Multi-attribute heuristic cross-references |

---

## 4. Core Subsystems & Operational Workflows

### 4.1. Automated Alert Triage & Root Cause Investigation (`/error-info`)
When an analyst opens an alert from the live stream or dashboard, NAAP triggers a coordinated investigation sequence:

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as React Frontend
    participant API as FastAPI Backend (/error-info)
    participant DB as SQLite (noc_automation_4.db)
    participant Diag as Diagnostic Runner
    participant AI as Gemini LLM / Rule Fallback

    Analyst->>UI: Selects Alert (event_id)
    UI->>API: GET /error-info?event_id={id}
    
    rect rgb(240, 248, 255)
    Note over API,DB: Step 1: Context Aggregation
    API->>DB: Fetch Device metadata (IP, Machine Type, Site)
    API->>DB: Fetch Event details & severity
    API->>DB: Query DEVICE_TICKET_MAP & SN_TICKETS for historical context
    DB-->>API: Return unified context payload
    end

    rect rgb(255, 250, 240)
    Note over API,Diag: Step 2: Preliminary Diagnostics
    par Ping Verification
        API->>Diag: ICMP Reachability (loss %, min/avg/max latency)
        Diag-->>API: Return Ping metrics
    and Route Tracing
        API->>Diag: Traceroute to destination IP
        Diag-->>API: Return Hops and latencies
    and Name Resolution
        API->>Diag: Reverse DNS lookup
        Diag-->>API: Return FQDN
    end
    end

    rect rgb(245, 255, 245)
    Note over API,AI: Step 3: Synthesis & Guidance
    API->>DB: Check cached TICKET_SOLUTION_SUMMARIES (< 10 min old)
    alt Cache hit
        DB-->>API: Return stored summary
    else Cache miss
        API->>AI: Send prompt (Event + Device + Diagnostic + Ticket History)
        AI-->>API: Return JSON (Hypothesis, Confidence, Next Steps)
        API->>DB: Cache summary into TICKET_SOLUTION_SUMMARIES
    end
    end

    API-->>UI: Return comprehensive triage payload (200 OK)
    UI-->>Analyst: Render side drawer with diagnostics, tickets, and AI guidance
```

### 4.2. Sites Management & Topology Drill-Down
The Sites page provides multi-dimensional visibility across the enterprise's 1,027 sites:
- **Search & Filter:** Instant filtering by site code, city name, and state.
- **Topology Drawer:** Clicking any site opens a wide detail drawer displaying:
  - Total device inventory for the facility.
  - Interactive table of managed devices (IP address, device type, recent alert counts).
  - Truncation with full-name hover tooltips and in-table search for large sites.
  - Direct links from site devices to corresponding active alerts and historical tickets.

### 4.3. Multi-Engine AI Synthesis Strategy
To ensure enterprise reliability, NAAP implements a three-tier fallback hierarchy for root-cause synthesis:

```mermaid
flowchart TD
    Prompt[Triage Context Assembled] --> CheckGemini{Is GEMINI_API_KEY set?}
    CheckGemini -- Yes --> CallGemini[Call Google Gemini 1.5 Flash API]
    CallGemini -- Success --> ReturnAI[Return LLM Hypothesis & Steps]
    CallGemini -- Failure / Timeout --> CheckGroq

    CheckGemini -- No --> CheckGroq{Is GROQ_API_KEY set?}
    CheckGroq -- Yes --> CallGroq[Call Groq LLaMA-3 API]
    CallGroq -- Success --> ReturnAI
    CallGroq -- Failure / Timeout --> RuleEngine

    CheckGroq -- No --> RuleEngine[Execute Deterministic Rule Engine]
    RuleEngine --> MatchSeverity{Check Event Category & Severity}
    MatchSeverity --> ReturnRule[Return Standard Operating Procedure Steps]
```

- **Primary:** Google Gemini 1.5 Flash provides high-speed structured JSON analysis.
- **Secondary:** Groq LLaMA-3 provides sub-second failover.
- **Deterministic SOP Engine:** Pre-compiled Standard Operating Procedures (SOPs) based on alert category (e.g., interface flaps, BGP resets, high CPU utilization) trigger if external cloud access is restricted or offline.

### 4.4. Asynchronous Data Ingestion Engine
When an administrator uploads fresh CSV or Excel exports (`/admin/ingest-excel`):
1. **Fast Response (HTTP 202 Accepted):** File structure is validated and an asynchronous `asyncio` background task is spawned immediately.
2. **Chunked Parsing & Normalization:** The ingest worker parses records in batches, normalizing site codes and timestamp formats.
3. **Cross-Reference Bridge:** New devices are automatically mapped to existing tickets using string similarity and site correlation algorithms.
4. **Client Polling:** The frontend polls `/admin/ingest-excel/{job_id}` with a progress bar, preventing browser timeouts during multi-megabyte uploads.

---

## 5. Security & Authentication Model

- **Authentication Scheme:** JSON Web Tokens (JWT) using HMAC-SHA256 (`HS256`).
- **Token Lifespan:** Access tokens expire after 60 minutes; refresh tokens expire after 7 days.
- **Password Storage:** Industry-standard PBKDF2-HMAC-SHA256 with 390,000 iterations (OWASP recommendation).
- **Role-Based Access Control (RBAC):**
  - `analyst`: Dashboard, Sites, Alerts console, Error-Info triage, diagnostics execution, solution summary view.
  - `admin`: All analyst permissions plus CSV ingestion, background job management, and system activity logs.
- **Token Invalidation:** Explicit logout adds the token's unique identifier (`jti`) to the `token_blocklist` table.

---

## 6. Repository Layout

The project structure is organized cleanly by responsibility:

```
noc-ps/
├── backend/                   # FastAPI application & test suite
│   ├── database/              # SQLite connection wrapper, migrations, and schema
│   ├── routers/               # Endpoint controllers (auth, metrics, sites, logs, etc.)
│   ├── services/              # Business logic (metrics_service, auth_service, etc.)
│   ├── utils/                 # Security (JWT, hashing), diagnostics, and exception handlers
│   ├── tests/                 # Automated Pytest suite (101 unit & integration tests)
│   └── requirements.txt       # Python dependencies
├── frontend/                  # React 19 SPA (Vite + Tailwind CSS + Lucide + Recharts)
│   ├── src/pages/             # UI views (Dashboard, Sites, Alerts, Tickets, Logs, Login)
│   ├── src/services/          # API client and local demo fallback handlers
│   └── package.json           # Frontend dependencies
├── data/                      # Data assets
│   ├── raw/                   # Source anonymized datasets (Events, Tickets)
│   ├── samples/               # Sample CSVs for upload testing
│   └── legacy_dbs/            # Inactive database snapshots
├── docs/                      # Technical documentation, diagrams, and schemas
├── scripts/                   # Benchmarks, query tests, and incremental updater
├── sql/                       # SQL migrations, sites seed dump, and query templates
├── noc_database_setup 1/      # Standalone initial ETL pipeline module
├── noc_automation_4.db        # Active database file (6,586 devices, 134,412 events)
├── start.sh / start.bat / start.ps1   # Multi-platform unified launch scripts
├── stop.sh / stop.bat                 # Multi-platform shutdown scripts
└── README.md                  # Quickstart documentation
```

---

## 7. Operations, Verification & Maintenance

### 7.1. Quick Launch
```bash
# Linux / macOS
./start.sh

# Windows (Command Prompt)
start.bat

# Windows (PowerShell)
.\start.ps1
```

### 7.2. Test Suite Execution
The backend includes a comprehensive 101-test suite covering authentication, RBAC, query logic, metrics calculation, and database migrations:
```bash
cd backend
PYTHONPATH=. .venv/bin/pytest tests/
```
**Verification Target:** `101 passed` with 0 failures.

### 7.3. Frontend Build Validation
```bash
cd frontend
npm run build
```
**Verification Target:** Clean compilation into `frontend/dist/`.
