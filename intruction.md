PS
1. Intelligent Network Alert Analysis
1. Alert Analysis
   Analyze alerts and collect relevant network logs and details.
2. Log Investigation
   Identify patterns, errors, anomalies and potential root causes.
3. Ticket History
   Review similar tickets, resolutions and previously successful fixes.
4. Preliminary Checks
   Perform connectivity, device health, configuration and service checks.
5. Solution Recommendation
   Leverage AI and vibe build a solution.

route
 1. post - /auth/login
 2. post - /auth/logout
 3. post - /auth/signup
 4. get - /get-metrics
 5. get - /get-logs
 6. get, post - /admin/activity-log
 7. post - /internal/traceroute
 8. post - /internal/ping
 9. post - /internal/nslookup
 10. get - /error-info
 11. post - /admin/ingest-excel

┌──────────────────────────────┐
│      1. EVENT TRIGGER        │
│                              │
│  Mock SolarWinds Monitoring  │
│                              │
│  🔴 P1                       │
│  AP-BLR-Flr3 Down            │
│                              │
│  🟡 P2                       │
│  SW-CORE-02                  │
│  High Packet Loss            │
│                              │
│  Device IP: 10.10.10.5       │
└──────────────┬───────────────┘
               │
               │ Alert Click Event
               ▼
┌─────────────────────────────────────────────────────┐
│                2. AUTOMATION ENGINE                 │
│                                                     │
│        ┌──────────────────────────────┐             │
│        │  Automation Orchestrator     │             │
│        │        API Backend           │             │
│        └──────────────┬───────────────┘             │
│                       │                             │
│       ┌───────────────┼────────────────┐            │
│       │               │                │            │
│       ▼               ▼                ▼            │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │  History &  │ │ Preliminary │ │   Solution  │   │
│ │   Tickets   │ │   Checks    │ │ Generation  │   │
│ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘   │
│        │               │                │           │
│        ▼               ▼                ▼           │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │  ServiceNow │ │ Diagnostic  │ │     LLM /   │   │
│ │ Ticket Dump │ │   Engine    │ │ Knowledge   │   │
│ │             │ │             │ │    Base     │   │
│ └─────────────┘ └─────────────┘ └─────────────┘   │
└────────────────────────┬────────────────────────────┘
                         │
                         │ Results
                         ▼
┌──────────────────────────────────────────────┐
│          3. NOC ANALYST DASHBOARD            │
│                                              │
│     Automated Troubleshooting Panel          │
│              AP-BLR-Flr3                     │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ HISTORICAL INFO                        │  │
│  │                                        │  │
│  │ Total Incidents (6m): 4                │  │
│  │ Last Outage: 2024-05-01                │  │
│  │ Past Fix: Replaced PoE Module          │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ PRELIMINARY CHECKS                     │  │
│  │                                        │  │
│  │ PING: 100% Packet Loss                 │  │
│  │ TRACEROUTE: Fail at Hop 3              │  │
│  │             (192.168.100.1)            │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │ SUGGESTED SOLUTION (LLM)               │  │
│  │                                        │  │
│  │ HYPOTHESIS:                            │  │
│  │ Switch port failure or power issue     │  │
│  │                                        │  │
│  │ RECOMMENDED STEPS:                     │  │
│  │ 1. Verify upstream switch status       │  │
│  │ 2. Perform hard power cycle            │  │
│  │ 3. Dispatch field tech                 │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘


Read both the excel sheet and db data. the db data is modified using these 2 excel sheet. i have also listed problem statement and solution diagram

you need to implement backend using fastapi
u need to query the db for result
find out a way to do tracerout, ping and nslookup (the cuerrent ip is not accessbile so add a flag in config to fake them if it is accessbile then call that endpoint)
use gemini api for error summary
create a script to merge the upload excel sheet and add them in the db. make a diff worker so that normal backend will not stuck in this work
make a proper component wise folder and code strcuture
work only in backend and add table in db if needed for login, logout and logs
do a proper documentation and even md for frontend team
make it scalable, modular
add metrics as much u can
u might need to make 3,4 diff sql query for fetching the solution since matching condiction might be diff for diff errors
do not work on frotned or do anything
make config.py and env file. do not hardcode anything
