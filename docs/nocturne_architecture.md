# Nocturne — System Architecture Diagram

High-level architecture of **Nocturne** (formerly NAAP): data in, storage, core services and the analyst experience. Today, SolarWinds and ServiceNow data arrives by CSV/Excel export through the Admin upload; live feeds are on the roadmap.

```mermaid
%%{init: {'theme':'base','themeVariables':{'fontFamily':'Calibri, Arial','primaryColor':'#E6F1FA','primaryBorderColor':'#004B87','lineColor':'#004B87'}}}%%
flowchart LR
    subgraph SRC["1 · DATA IN"]
        SW["SolarWinds<br/>alert event logs"]
        SN["ServiceNow<br/>incident tickets"]
        INV["Site / device list<br/>sites · devices"]
        UP["Admin upload<br/>CSV / XLS / XLSX<br/>Phase 2: live syslog + ServiceNow API"]
    end
    subgraph STORE["2 · STORE"]
        ING["Async ingest worker<br/>auto-detect headers · link tickets to devices"]
        DB[("SQLite (indexed)<br/>devices · sites · event_logs<br/>sn_tickets · device_ticket_map<br/>solution summaries (10-min cache)")]
        AUD["Audit trail<br/>activity_logs + latency"]
    end
    subgraph CORE["3 · NOCTURNE CORE (FastAPI)"]
        AUTH["JWT auth · RBAC (analyst / admin)"]
        LOG["Activity-logger middleware"]
        TRI["Alert investigation engine · /error-info"]
        DIAG["Diagnostics<br/>ping · traceroute · nslookup"]
        AI["AI synthesis<br/>hypothesis + SOP steps"]
    end
    subgraph UX["4 · EXPERIENCE"]
        UI["React 19 console<br/>Dashboard · Alert drawer · Sites · Tickets · Admin"]
        USER(["NOC analyst"])
    end
    subgraph EXT["External"]
        direction TB
        G["Gemini 3.5 Flash"] --> GR["Groq (failover)"] --> RB["Built-in rule engine (always available)"]
        NET["Host network stack"]
    end
    SW --> UP
    SN --> UP
    INV --> UP
    UP --> ING --> DB
    DB <--> TRI
    UI <--> AUTH --> LOG --> TRI
    TRI --> DIAG
    TRI --> AI
    DIAG -.-> NET
    AI -.-> G
    AI --> DB
    LOG --> AUD
    USER <--> UI
    classDef sw fill:#FDF0DC,stroke:#F99D1C,color:#0F172A
    classDef sn fill:#E3F5EC,stroke:#2E7D5B,color:#0F172A
    classDef core fill:#004B87,stroke:#004B87,color:#fff
    classDef dark fill:#00283F,stroke:#00283F,color:#fff
    class SW sw
    class SN sn
    class TRI core
    class DB,UI dark
```
