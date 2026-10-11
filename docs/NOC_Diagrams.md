# Nocturne — Technical Diagrams & Systems Architecture

This document holds the architectural and workflow diagrams for **Nocturne** (formerly NAAP), the NOC alert-investigation platform that connects SolarWinds events, ServiceNow history and live diagnostics. All diagrams use Mermaid and were checked against the codebase (routers, services, migrations and `config.py`).

| # | Diagram | Answers |
|---|---|---|
| 1 | Where Nocturne fits | How does it relate to SolarWinds and ServiceNow? |
| 2 | System context & layered architecture | What are the components and boundaries? |
| 3 | End-to-end alert investigation sequence | What happens when an analyst opens an alert? |
| 4 | Entity-relationship diagram | How is the data modelled? |
| 5 | Multi-tier AI synthesis | What if Gemini or Groq is down? |
| 6 | Asynchronous ingestion pipeline | How do exports get in? |
| 7 | RBAC & use cases | Who can do what? |
| 8 | Roadmap: demo to live integrations | What is real today vs. planned? |

---

## 1. Where Nocturne Fits
Nocturne is the layer between the monitor (SolarWinds) and the ticket system (ServiceNow). It replaces neither.

```mermaid
flowchart LR
    SW["SolarWinds<br/>Monitoring & alerting<br/>(monitor of record)"]
    SN["ServiceNow<br/>Incident history<br/>(system of record)"]
    INV["Site & device inventory<br/>which device sits at which site"]

    subgraph NOC ["Nocturne: the layer in between"]
        direction TB
        C1["Correlate alert, device, site and tickets"]
        C2["Run ping, traceroute and DNS"]
        C3["Reuse what fixed it last time"]
        C4["Suggest ordered SOP steps (AI)"]
        C1 --> C2 --> C3 --> C4
    end

    ANALYST(["NOC analyst<br/>one screen, one click"])

    SW -->|events| C1
    SN -->|ticket history| C1
    INV -->|topology| C1
    C4 --> ANALYST
    ANALYST -.->|decides and acts| SN

    classDef sw fill:#FDF0DC,stroke:#F99D1C,color:#0F172A
    classDef sn fill:#E3F5EC,stroke:#2E7D5B,color:#0F172A
    classDef core fill:#004B87,stroke:#004B87,color:#fff
    class SW sw
    class SN sn
    class C1,C2,C3,C4 core
```

---

## 2. System Context & Layered Architecture
How data sources, the client, the API, persistence and external AI/network subsystems interact.

```mermaid
flowchart TB
    subgraph Sources ["Data Sources (exports today, live feeds planned)"]
        SW["SolarWinds event logs<br/>CSV / Excel"]
        SN["ServiceNow tickets<br/>CSV / Excel"]
        INV["Site / device inventory"]
    end

    subgraph Presentation ["Presentation Layer (Client)"]
        Browser["React 19 SPA (Vite + Tailwind CSS)<br/>• Dashboard & real-time KPIs<br/>• Alert investigation drawer<br/>• Sites management & topology drawer<br/>• Tickets<br/>• Admin ingest console"]
    end

    subgraph ServiceLayer ["API & Orchestration Layer (FastAPI)"]
        Router["FastAPI application (Uvicorn)"]
        AuthMiddleware["JWT auth & RBAC guard<br/>(HS256, admin / analyst)"]
        AuditMiddleware["Activity-logger middleware<br/>(latency, status, client IP)"]

        InvestigationEngine["Alert investigation engine<br/>GET /error-info"]
        DiagRunner["Diagnostics engine<br/>(ping, traceroute, nslookup)"]
        AIService["AI synthesis engine<br/>(Gemini → Groq → rule engine)"]
        IngestWorker["Async ingest worker<br/>(pandas parser, device-ticket linker)"]
    end

    subgraph Persistence ["Data & Storage Layer (SQLite 3)"]
        DB[("noc_automation_4.db<br/>• devices & sites<br/>• event logs<br/>• ServiceNow tickets<br/>• device-ticket links<br/>• cached AI summaries")]
    end

    subgraph External ["External Intelligence & Diagnostics"]
        GeminiAPI["Google Gemini API<br/>(primary LLM)"]
        GroqAPI["Groq API<br/>(failover LLM)"]
        NetworkStack["Host network stack<br/>(live checks when FAKE_DIAGNOSTICS=False)"]
    end

    Browser -->|HTTPS REST / JWT bearer| Router
    Router --> AuthMiddleware --> AuditMiddleware
    AuditMiddleware --> InvestigationEngine
    AuditMiddleware --> IngestWorker

    InvestigationEngine -->|context query| DB
    InvestigationEngine -->|run checks| DiagRunner
    DiagRunner -.->|ICMP / UDP / DNS| NetworkStack
    InvestigationEngine -->|generate guidance| AIService

    AIService -.->|primary| GeminiAPI
    AIService -.->|failover| GroqAPI
    AIService -->|cache summary| DB

    SW -->|admin upload| IngestWorker
    SN -->|admin upload| IngestWorker
    INV -->|seed / upload| IngestWorker
    IngestWorker -->|batch upserts| DB
```

---

## 3. Sequence Diagram: End-to-End Automated Alert Investigation
When an analyst clicks an alert, Nocturne runs the investigation in a single request.

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as NOC Analyst
    participant UI as React Console
    participant API as FastAPI (/error-info)
    participant DB as SQLite DB
    participant Diag as Diagnostic Runner
    participant AI as Gemini / Groq / Rules

    Analyst->>UI: Selects alert card (event_id)
    UI->>API: GET /error-info?event_id=1042

    rect rgb(30, 35, 45)
    Note over API,DB: Phase 1: Context aggregation
    API->>DB: Resolve event, device and event type
    API->>DB: Master query over device_ticket_map and sn_tickets
    DB-->>API: Unified context record
    end

    rect rgb(35, 45, 30)
    Note over API,Diag: Phase 2: Preliminary diagnostics
    API->>Diag: ping, traceroute and nslookup on device IP
    Diag-->>API: Loss %, RTT, hop list, reverse DNS
    end

    rect rgb(45, 35, 30)
    Note over API,AI: Phase 3: Root-cause synthesis
    API->>DB: Check ticket_solution_summaries (TTL 10 min)
    alt Cache hit (AI or analyst summary)
        DB-->>API: Return existing synthesis
    else Cache miss, stale, or rule-based only
        API->>AI: Minimal prompt (event, device, ping, up to 3 tickets)
        AI-->>API: JSON (hypothesis, steps, confidence)
        API->>DB: Store in ticket_solution_summaries
    end
    end

    API-->>UI: Full analysis JSON (200 OK)
    UI-->>Analyst: Drawer with context, diagnostics and action plan
```

> With the default `FAKE_DIAGNOSTICS=True`, Phase 2 returns simulated results. Set it to `False` to run real system commands.

---

## 4. Entity-Relationship Diagram (ERD)
The relational schema linking sites, devices, monitoring events and ServiceNow tickets, plus the operational tables for auth, audit and ingest.

```mermaid
erDiagram
    USERS {
        int id PK
        string username
        string email
        string hashed_password
        string role
        int is_active
        datetime created_at
    }

    SITES {
        string code PK
        string label
        string city
        string state
        string address
        string updated_at
    }

    DEVICES {
        string device_id PK
        int node_id
        string device_name
        string ip_address
        string site_code
        string site_name
        string machine_type
        string vendor
        string location
    }

    EVENT_TYPE_LOOKUP {
        int event_type_id PK
        string event_type_name
        string severity
        string category
    }

    EVENT_LOGS {
        int event_id PK
        string event_time
        int event_type_id FK
        string event_type_name
        string message
        int device_id FK
        int current_status
        string raw_detail
    }

    SN_TICKETS {
        string ticket_id PK
        string ticket_number
        string ticket_type
        string state
        string created_on
        string updated_on
        string closed_at
        string assignment_group
        string short_description
        string description
        string work_notes
        string extracted_site_codes
        string extracted_ips
        string extracted_device_names
    }

    DEVICE_TICKET_MAP {
        string id PK
        int device_id FK
        int ticket_id FK
        string match_type
        string match_value
        float confidence
    }

    TICKET_SOLUTION_SUMMARIES {
        int id PK
        int event_id
        string hypothesis
        string recommended_steps
        string confidence
        string generated_by
        string source_tickets
        datetime created_at
        datetime updated_at
    }

    ACTIVITY_LOGS {
        int id PK
        int user_id FK
        string action
        string endpoint
        string ip_address
        string request_body
        int response_status
        string user_agent
        float duration_ms
        string target_resource
        datetime created_at
    }

    INGEST_JOBS {
        int id PK
        string filename
        string status
        datetime started_at
        datetime completed_at
        int rows_processed
        string error_message
        int triggered_by FK
    }

    TOKEN_BLOCKLIST {
        int id PK
        string jti
        datetime expires_at
        datetime created_at
    }

    SITES ||--o{ DEVICES : "houses (1:N)"
    DEVICES ||--o{ EVENT_LOGS : "generates (1:N)"
    EVENT_TYPE_LOOKUP ||--o{ EVENT_LOGS : "classifies (1:N)"
    DEVICES ||--o{ DEVICE_TICKET_MAP : "associated with (1:N)"
    SN_TICKETS ||--o{ DEVICE_TICKET_MAP : "resolves (1:N)"
    EVENT_LOGS ||--o| TICKET_SOLUTION_SUMMARIES : "receives advice (1:1)"
    USERS ||--o{ ACTIVITY_LOGS : "triggers (1:N)"
    USERS ||--o{ INGEST_JOBS : "uploads (1:N)"
```

- `device_ticket_map.match_type` is one of `site_code`, `device_name`, `ip_address`; `confidence` is 0.0–1.0.
- `ticket_solution_summaries.generated_by` records the source: `gemini`, `groq`, `rule-based` or an analyst edit.
- `DEVICES.site_code` references `SITES.code` by convention (no enforced foreign key). `devices.device_id` is `TEXT` in the baseline schema; SQLite type affinity handles the join to `event_logs.device_id`.

---

## 5. Multi-Tier AI Synthesis Hierarchy
Fail-safe logic so analysts always receive remediation guidance, even during API downtime or network isolation.

```mermaid
flowchart TD
    Start["Analyst selects alert"] --> Cache{"Fresh cached summary?<br/>(AI or analyst, under 10 min)"}
    Cache -->|Yes| RenderUI
    Cache -->|"No, or rule-based only"| BuildPrompt["Assemble minimal context<br/>device + event + ping + up to 3 tickets"]
    BuildPrompt --> CheckGemini{"GEMINI_API_KEY set?"}

    CheckGemini -->|Yes| CallGemini["Call Gemini 3.5 Flash<br/>structured JSON prompt"]
    CallGemini -->|Success| SaveCache["Save to ticket_solution_summaries"]
    CallGemini -->|"Error, rate limit or bad JSON"| CheckGroq

    CheckGemini -->|"No"| CheckGroq{"GROQ_API_KEY set?"}
    CheckGroq -->|Yes| CallGroq["Call Groq (openai/gpt-oss-20b)<br/>fast failover model"]
    CallGroq -->|Success| SaveCache
    CallGroq -->|"Error or bad JSON"| RuleEngine

    CheckGroq -->|"No"| RuleEngine["Deterministic rule engine"]
    RuleEngine --> GenerateSOP["SOP from event category and ping result<br/>always succeeds, no cloud needed"]

    SaveCache --> RenderUI["Render actionable plan to analyst"]
    GenerateSOP --> RenderUI
```

---

## 6. Asynchronous Data Ingestion Pipeline
How large SolarWinds and ServiceNow exports are ingested without blocking the API or freezing the UI.

```mermaid
flowchart TD
    Admin["Administrator"] -->|"Uploads SolarWinds events or ServiceNow tickets (CSV / Excel)"| PostAPI["POST /admin/ingest-excel"]

    subgraph WebAPI ["FastAPI REST server"]
        PostAPI --> ValidateFile{"Size limit OK and headers recognised?"}
        ValidateFile -->|"Invalid"| Return400["HTTP 4xx error"]
        ValidateFile -->|"Valid: events or tickets"| CreateJob["Create ingest_jobs record<br/>status: pending"]
        CreateJob --> SpawnTask["Spawn asyncio background worker"]
        SpawnTask --> Return202["HTTP 202 Accepted<br/>returns job_id"]
    end

    subgraph FrontendUI ["React application"]
        Return202 --> PollJob["Poll GET /admin/ingest-excel/{job_id}<br/>progress and status"]
    end

    subgraph BackgroundWorker ["Async ingest worker"]
        SpawnTask -.-> SetRunning["Update status: running"]
        SetRunning --> ParseFile["Parse CSV / Excel with pandas<br/>auto-map column names"]
        ParseFile --> NormalizeData["Normalise timestamps and site codes"]
        NormalizeData --> BatchUpsert["UPSERT into SQLite<br/>devices, events or tickets"]
        BatchUpsert --> RebuildMap["Link devices to tickets<br/>site_code, device_name, ip_address<br/>with confidence scores"]
        RebuildMap --> MarkDone["Update status: completed (or failed with error)"]
    end

    MarkDone --> PollJob
    PollJob --> UIComplete["Display ingest summary banner"]
```

> The worker runs in-process and is not durable: an API restart can interrupt an active import. A durable queue is on the Phase 2 roadmap.

---

## 7. Role-Based Access Control (RBAC) & Use Cases

```mermaid
flowchart LR
    subgraph Roles ["User roles"]
        Analyst((NOC Analyst))
        Admin((NOC Administrator))
    end

    subgraph Capabilities ["Platform capabilities"]
        KPI[View operational dashboard & live metrics]
        Sites[Search sites & inspect device drawers]
        Tickets[Browse ServiceNow ticket history]
        Investigate[Run alert investigation & AI synthesis]
        Diagnostics[Run ping & traceroute checks]
        Ingest[Upload CSV / Excel datasets]
        Jobs[Track ingest jobs]
        Audit[View system activity & latency logs]
    end

    Analyst --> KPI
    Analyst --> Sites
    Analyst --> Tickets
    Analyst --> Investigate
    Analyst --> Diagnostics

    Admin --> KPI
    Admin --> Sites
    Admin --> Tickets
    Admin --> Investigate
    Admin --> Diagnostics
    Admin --> Ingest
    Admin --> Jobs
    Admin --> Audit

    style Analyst fill:#10b981,stroke:#047857,color:#ffffff
    style Admin fill:#3b82f6,stroke:#1d4ed8,color:#ffffff
```

---

## 8. Roadmap: From Demo to Live Integrations
What is real today (solid) versus planned (dashed).

```mermaid
flowchart LR
    subgraph Today ["Today: demo build"]
        T1["SolarWinds export<br/>CSV / Excel upload"]
        T2["ServiceNow export<br/>CSV / Excel upload"]
        T3["Investigation drawer + 3-tier AI"]
        T4["JWT login, analyst / admin"]
    end

    subgraph P2 ["Phase 2: 3-6 months"]
        P2a["Live syslog / Kafka<br/>from SolarWinds"]
        P2b["Bidirectional ServiceNow sync"]
        P2d["Durable ingest queue"]
    end

    subgraph P3 ["Phase 3: 6-12 months"]
        P3a["Pre-approved one-click actions<br/>e.g. port bounce"]
        P3b["Automated carrier tickets"]
        P3c["Predictive site health"]
    end

    T1 -.-> P2a
    T2 -.-> P2b
    T3 -.-> P2d
    P2a -.-> P3a
    P2b -.-> P3b
    P2b -.-> P3c

    classDef today fill:#E3F5EC,stroke:#109564,color:#0F172A
    classDef plan fill:#FDF0DC,stroke:#D97706,color:#0F172A,stroke-dasharray: 4 3
    class T1,T2,T3,T4 today
    class P2a,P2b,P2d,P3a,P3b,P3c plan
```
