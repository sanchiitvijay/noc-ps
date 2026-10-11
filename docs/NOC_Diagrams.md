# NOC Automation Platform — Technical Diagrams & Systems Architecture

This document contains the complete, authoritative architectural and workflow diagrams for the Network Alerts Automation Platform (NAAP). All diagrams use standardized Mermaid notation and precisely match the operational codebase.

---

## 1. System Context & Layered Architecture
This diagram outlines how clients, backend micro-services, persistence, and external AI/network subsystems interact.

```mermaid
flowchart TB
    subgraph Presentation ["Presentation Layer (Client)"]
        Browser["React 19 SPA (Vite + Tailwind CSS)<br/>• Dashboard & Real-Time KPIs<br/>• Sites Management & Topology Drawer<br/>• Alert Investigation Panel<br/>• Admin CSV Ingest Console"]
    end

    subgraph ServiceLayer ["API & Orchestration Layer (FastAPI)"]
        Router["FastAPI Application (Uvicorn / Python 3.14)"]
        AuthMiddleware["JWT Authentication & RBAC Guard<br/>(HS256 Token Validation, User Roles)"]
        AuditMiddleware["Activity Logger Middleware<br/>(Execution Latency, Status, Client IP)"]
        
        TriageEngine["Alert Triage Engine (/error-info)"]
        DiagRunner["Network Diagnostics Engine<br/>(ICMP Ping, Traceroute, Reverse DNS)"]
        AIService["AI Synthesis Engine<br/>(Gemini 3.5 Flash -> Groq LLaMA-3 -> Rule Engine)"]
        IngestWorker["Async Background Ingest Worker<br/>(Pandas Chunked Parser, Entity Linker)"]
    end

    subgraph Persistence ["Data & Storage Layer (SQLite 3)"]
        DB[("noc_automation_4.db (Indexed SQLite)<br/>• 6,586 Devices<br/>• 1,027 Sites<br/>• 134,412 Event Logs<br/>• 456 ServiceNow Tickets<br/>• 2,314 Cross-Reference Links")]
        DiskAssets["data/ Raw Lake<br/>• Raw CSV Datasets<br/>• Upload Samples"]
    end

    subgraph External ["External Intelligence & Diagnostics"]
        GeminiAPI["Google Gemini API (Cloud LLM)"]
        GroqAPI["Groq Cloud API (Backup LLM)"]
        NetworkStack["Host OS Socket Stack (Live Diagnostics)"]
    end

    Browser -->|HTTPS REST Requests / JWT Bearer| Router
    Router --> AuthMiddleware --> AuditMiddleware
    AuditMiddleware --> TriageEngine
    AuditMiddleware --> IngestWorker

    TriageEngine -->|Context Query| DB
    TriageEngine -->|Run Checks| DiagRunner
    DiagRunner -.->|ICMP / UDP| NetworkStack
    TriageEngine -->|Generate Guidance| AIService
    
    AIService -.->|Primary| GeminiAPI
    AIService -.->|Failover| GroqAPI
    AIService -->|Store Summary| DB

    IngestWorker -->|Batch Inserts| DB
    DiskAssets -.->|Admin Upload| IngestWorker
```

---

## 2. Sequence Diagram: End-to-End Automated Alert Triage
When an analyst clicks an alert, NAAP automates the entire investigation pipeline in a single request.

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as NOC Analyst
    participant UI as React Console
    participant API as FastAPI (/error-info)
    participant DB as SQLite DB
    participant Diag as Diagnostic Runner
    participant AI as Gemini LLM / Rules

    Analyst->>UI: Selects Alert Card (event_id)
    UI->>API: GET /error-info?event_id=1042
    
    rect rgb(30, 35, 45)
    Note over API,DB: Phase 1: Context Aggregation
    API->>DB: Query Event details, Severity, & Timestamp
    API->>DB: Query Device details (IP, Site Code, Hardware Type)
    API->>DB: Query DEVICE_TICKET_MAP & SN_TICKETS for history
    DB-->>API: Return unified context record
    end

    rect rgb(35, 45, 30)
    Note over API,Diag: Phase 2: Preliminary Diagnostics
    par Diagnostic Execution
        API->>Diag: Execute Ping (Packet loss %, Latency)
        Diag-->>API: Return Ping results
    and Route Verification
        API->>Diag: Execute Traceroute (Hop count, RTT)
        Diag-->>API: Return Hop sequence
    and Name Resolution
        API->>Diag: Reverse DNS Lookup
        Diag-->>API: Return FQDN
    end
    end

    rect rgb(45, 35, 30)
    Note over API,AI: Phase 3: Root Cause Synthesis
    API->>DB: Check TICKET_SOLUTION_SUMMARIES (Cache TTL: 10m)
    alt Cache Hit
        DB-->>API: Return existing synthesis
    else Cache Miss
        API->>AI: Send prompt (Event + Device + Diag + Tickets)
        AI-->>API: Return JSON (Root Cause Hypothesis + SOP Next Steps)
        API->>DB: Store solution in TICKET_SOLUTION_SUMMARIES
    end
    end

    API-->>UI: Return full analysis JSON (Status 200 OK)
    UI-->>Analyst: Render Drawer with context, diagnostics, & action plan
```

---

## 3. Entity-Relationship Diagram (ERD)
The relational schema linking physical sites, managed devices, monitoring alerts, and historical ServiceNow tickets.

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
        string site_code PK
        string site_name
        string state
    }

    DEVICES {
        int device_id PK
        string device_name
        string ip_address
        string site_code FK
        string machine_type
    }

    EVENT_TYPE_LOOKUP {
        int event_type_id PK
        string event_type_name
        string severity
        string category
    }

    EVENT_LOGS {
        int event_id PK
        int device_id FK
        int event_type_id FK
        string event_time
        string message
    }

    SN_TICKETS {
        int ticket_id PK
        string ticket_number
        string state
        string priority
        string short_description
        string close_notes
    }

    DEVICE_TICKET_MAP {
        int id PK
        int device_id FK
        int ticket_id FK
        float confidence
    }

    TICKET_SOLUTION_SUMMARIES {
        int id PK
        int event_id FK
        string model_used
        string hypothesis
        string recommended_actions
        datetime created_at
    }

    ACTIVITY_LOGS {
        int id PK
        int user_id FK
        string action
        string ip_address
        int status_code
        float latency_ms
        datetime created_at
    }

    SITES ||--o{ DEVICES : "houses (1:N)"
    DEVICES ||--o{ EVENT_LOGS : "generates (1:N)"
    EVENT_TYPE_LOOKUP ||--o{ EVENT_LOGS : "classifies (1:N)"
    DEVICES ||--o{ DEVICE_TICKET_MAP : "associated with (1:N)"
    SN_TICKETS ||--o{ DEVICE_TICKET_MAP : "resolves (1:N)"
    EVENT_LOGS ||--o| TICKET_SOLUTION_SUMMARIES : "receives advice (1:1)"
    USERS ||--o{ ACTIVITY_LOGS : "triggers (1:N)"
```

---

## 4. Multi-Tier AI Synthesis Hierarchy
Fail-safe logic ensuring analysts always receive recommended remediation steps, even during API downtime or network isolation.

```mermaid
flowchart TD
    Start([Analyst Selects Alert]) --> BuildPrompt[Assemble Unified Context<br/>Device + Event + Diagnostics + Ticket History]
    BuildPrompt --> CheckGemini{Google Gemini<br/>API Available?}

    CheckGemini -- Yes --> CallGemini[Call Gemini 3.5 Flash<br/>Structured JSON Prompt]
    CallGemini -- Success --> SaveCache[Save to TICKET_SOLUTION_SUMMARIES]
    CallGemini -- Rate Limit / Error --> CheckGroq

    CheckGemini -- No / Disabled --> CheckGroq{Groq LLaMA-3<br/>API Available?}
    CheckGroq -- Yes --> CallGroq[Call Groq LLaMA-3<br/>Fast Failover Model]
    CallGroq -- Success --> SaveCache
    CallGroq -- Error --> RuleEngine

    CheckGroq -- No / Disabled --> RuleEngine[Execute Deterministic Rule Engine]
    RuleEngine --> MatchRules{Evaluate Category & Severity<br/>• Interface / BGP / Flap<br/>• Memory / CPU / Temp<br/>• Link Down / Route Loss}
    MatchRules --> GenerateSOP[Synthesize Standard Operating Procedure<br/>(Deterministic Expert Rules)]
    
    SaveCache --> RenderUI([Render Actionable Plan to Analyst])
    GenerateSOP --> RenderUI
```

---

## 5. Asynchronous Data Ingestion Pipeline
Demonstrates how large CSV/Excel files are ingested without blocking the REST API or freezing the UI.

```mermaid
flowchart TD
    Admin([Administrator]) -->|Uploads CSV / Excel| PostAPI[POST /admin/ingest-excel]
    
    subgraph WebAPI ["FastAPI REST Server"]
        PostAPI --> ValidateFile{Validate Headers & Structure}
        ValidateFile -- Invalid Format --> Return400[HTTP 400 Bad Request]
        ValidateFile -- Valid Structure --> CreateJob[Create Record in ingest_jobs<br/>Status = 'queued']
        CreateJob --> SpawnTask[Spawn asyncio Background Worker]
        SpawnTask --> Return202[HTTP 202 Accepted<br/>Returns job_id]
    end

    subgraph FrontendUI ["React Application"]
        Return202 --> PollJob[Poll GET /admin/ingest-excel/{job_id}<br/>Progress Bar & Status Updates]
    end

    subgraph BackgroundWorker ["Async Ingestion Worker"]
        SpawnTask -.-> SetProcessing[Update Status = 'processing']
        SetProcessing --> ChunkRead[Read CSV in 10,000-Row Chunks]
        ChunkRead --> NormalizeData[Normalize Timestamps & Site Codes]
        NormalizeData --> BatchUpsert[Batch UPSERT into SQLite<br/>Devices / Events / Tickets]
        BatchUpsert --> RebuildMap[Recalculate DEVICE_TICKET_MAP<br/>Confidence Scores]
        RebuildMap --> MarkDone[Update Status = 'completed']
    end

    MarkDone --> PollJob
    PollJob --> UIComplete[Display Ingest Summary Banner]
```

---

## 6. Role-Based Access Control (RBAC) & Use Cases

```mermaid
flowchart LR
    subgraph Roles ["User Roles"]
        Analyst((NOC Analyst))
        Admin((NOC Administrator))
    end

    subgraph Capabilities ["Platform Capabilities"]
        KPI[View Operational Dashboard & Live Metrics]
        Sites[Search Sites & Inspect Device Drawers]
        Triage[Execute Alert Investigation & AI Synthesis]
        Diagnostics[Run Ping & Traceroute Checks]
        Ingest[Upload CSV/Excel Datasets]
        Audit[View System Activity & Latency Logs]
    end

    Analyst --> KPI
    Analyst --> Sites
    Analyst --> Triage
    Analyst --> Diagnostics

    Admin --> KPI
    Admin --> Sites
    Admin --> Triage
    Admin --> Diagnostics
    Admin --> Ingest
    Admin --> Audit

    style Analyst fill:#10b981,stroke:#047857,color:#ffffff
    style Admin fill:#3b82f6,stroke:#1d4ed8,color:#ffffff
```
