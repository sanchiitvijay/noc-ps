# NOC Automation System Diagrams

Below are the architectural and workflow diagrams for the NOC Automation platform. These diagrams are rendered using Mermaid.

## 1. Sequence Diagram: Automated Alert Analysis
This diagram maps out the core workflow when an analyst requests root cause analysis for a network alert.

```mermaid
sequenceDiagram
    actor Analyst
    participant UI as NOC Dashboard
    participant API as FastAPI Backend
    participant DB as SQLite DB
    participant Diag as Diagnostic Engine
    participant LLM as Gemini API

    Analyst->>UI: Click on Network Alert
    UI->>API: GET /error-info (device_id, event_id)
    
    rect rgb(30, 30, 30)
    Note over API,DB: Data Gathering
    API->>DB: Query Device & Event details
    DB-->>API: Return Context
    API->>DB: Query ServiceNow Tickets
    DB-->>API: Return Historical Incident Data
    end
    
    rect rgb(30, 30, 30)
    Note over API,Diag: Preliminary Checks
    par Diagnostic Execution
        API->>Diag: Execute internal/ping
        Diag-->>API: Return Packet Loss & RTT
    and
        API->>Diag: Execute internal/traceroute
        Diag-->>API: Return Network Hops
    end
    end
    
    rect rgb(30, 30, 30)
    Note over API,LLM: AI Synthesis
    API->>LLM: Send structured prompt (Context + Diagnostics)
    LLM-->>API: Return Hypothesis & Steps (JSON)
    end
    
    API-->>UI: Return Full Analysis Panel
    UI-->>Analyst: Render actionable solution
```

---

## 2. Entity-Relationship Diagram (ERD)
This diagram illustrates the relational database schema, highlighting how devices map to both historical ServiceNow tickets and active event logs.

```mermaid
erDiagram
    USERS {
        int id PK
        string username
        string role
        int is_active
    }
    
    DEVICES {
        int device_id PK
        string device_name
        string ip_address
        string site_code
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
        string short_description
    }
    
    DEVICE_TICKET_MAP {
        int id PK
        int device_id FK
        int ticket_id FK
        float confidence
    }

    DEVICES ||--o{ EVENT_LOGS : "generates"
    EVENT_TYPE_LOOKUP ||--o{ EVENT_LOGS : "categorizes"
    DEVICES ||--o{ DEVICE_TICKET_MAP : "associated with"
    SN_TICKETS ||--o{ DEVICE_TICKET_MAP : "resolves"
```

---

## 3. Flow Diagram: Background Data Ingestion
This chart demonstrates how large CSV/Excel files (Event dumps or ServiceNow ticket dumps) are ingested asynchronously without blocking the main REST API.

```mermaid
flowchart TD
    A([Admin User]) -->|Uploads CSV| B(POST /admin/ingest-excel)
    
    subgraph FastAPI Application
        B --> C{File Validation}
        C -- Invalid --> D[Return 400 Bad Request]
        C -- Valid --> E[Create Ingest Job in DB]
        E --> F[Spawn asyncio Background Task]
        F --> G[Return 202 Accepted to User immediately]
    end
    
    subgraph Async Ingest Worker
        F -.-> H[Parse CSV using Pandas]
        H --> I{Identify File Type}
        I -- Ticket Data --> J[Map to SN_TICKETS Table]
        I -- Event Data --> K[Map to EVENT_LOGS Table]
        J --> L[Insert/Update SQLite DB]
        K --> L
        L --> M[Update Ingest Job Status = 'completed']
    end
```

---

## 4. Use Case Diagram
This outlines the primary system interactions based on user roles (Admin vs. NOC Analyst).

```mermaid
flowchart LR
    %% Actor nodes
    Admin((Admin))
    Analyst((NOC Analyst))
    System((Background System))

    %% Use Cases
    Upload[Upload Historical Data Dumps]
    Audit[View API Activity Logs]
    
    Metrics[View Real-Time Metrics & Trends]
    Logs[Query & Filter Network Events]
    Diag[Run Manual Ping/Traceroute]
    AI[Generate AI Root Cause Analysis]

    LogUser[Activity Logger Middleware]
    
    %% Relationships
    Admin ===> Upload
    Admin ===> Audit
    Admin -.-> Metrics
    
    Analyst ===> Metrics
    Analyst ===> Logs
    Analyst ===> Diag
    Analyst ===> AI
    
    System -.-> LogUser
    LogUser -.-> Audit
    
    style Admin fill:#2a50a3,stroke:#fff,stroke-width:2px,color:#fff
    style Analyst fill:#257a3e,stroke:#fff,stroke-width:2px,color:#fff
    style System fill:#4a4a4a,stroke:#fff,stroke-width:2px,color:#fff
```
