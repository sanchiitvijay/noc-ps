# Data Quality Report - NOC Automation Project

> **Role:** Database Engineer | **Date:** October 4, 2026  
> **Database:** `noc_automation.db` (47.7 MB, SQLite)

---

## Executive Summary

The new datasets **significantly improve** over the previous anonymized versions. The critical `DeviceName` and `IPAddress` fields now contain **real values**, enabling the relational bridge between Event Logs and ServiceNow Tickets that was previously impossible.

| Metric | Value | Assessment |
|--------|-------|-----------|
| Event Logs Loaded | 134,385 | Full 30-day dataset |
| Devices Registered | 6,583 | Extracted from events |
| Tickets Loaded | 442 | All NOC tickets |
| Cross-Reference Links Created | 2,314 | **Working bridge** |
| Devices Linked to Tickets | 704 (10.7%) | Needs more ticket data |
| Tickets Linked to Devices | 277 (62.7%) | Good coverage |

---

## 1. Anonymization Status

### What is Fixed (vs. Previous Datasets)

| Field | Previous | Current | Status |
|-------|----------|---------|--------|
| `DeviceName` | `[DEVICE_ID]` everywhere | Real names (e.g., `0501-Lakewood-NJ-N3048P-40`) | **FIXED** |
| `IPAddress` | `[IP_ADDRESS]` | Real IPs (6,581 unique, e.g., `10.82.216.151`) | **FIXED** |
| SN `short_description` | Anonymized | Real descriptions with FEI codes | **FIXED** |
| SN `description` | Anonymized | Contains real IPs (108/442 tickets) | **FIXED** |
| SN `work_notes` | Anonymized | Contains real troubleshooting steps | **FIXED** |

### What is Still Broken

| Field | Issue | Impact | Severity |
|-------|-------|--------|----------|
| `EventTime` | Prefixed with `[DEVICE_ID]`, **date portion is missing** | Cannot determine WHICH DAY an event occurred. Only time (HH:MM:SS) preserved | **CRITICAL** |
| `opened_by` | ALL 442 rows are NULL | Cannot track who created tickets | Medium |
| `assigned_to` | ALL 442 rows are NULL | Cannot track who resolved tickets | Medium |
| `work_notes_list` | ALL 442 rows are NULL | Missing structured work notes | Low |
| Some `Location` fields | Contains `[ADDRESS]` tags | Partial location data lost | Low |
| Some `Message` fields | Contains `[DEVICE_ID]`/`[IP_ADDRESS]` tags | Partial detail lost, but DeviceName column compensates | Low |
| Some ticket IPs | Partially masked (e.g., `10.141.82.XXX`) | 5 tickets have unusable IPs | Low |

**CRITICAL: The missing date in EventTime is the most critical remaining issue.** Without dates, we cannot correlate "Device X went down on July 10" with "Ticket INC2180572 opened on July 10 for Device X." Time-based correlation is severely limited. This should be escalated to the data team immediately.

---

## 2. Cross-Reference Results

The bridge between Event Logs and ServiceNow Tickets is built using 3 matching strategies:

### Strategy Performance

| Strategy | Links | Confidence | Unique Devices | Unique Tickets | Notes |
|----------|-------|-----------|----------------|----------------|-------|
| **Site/FEI Code** | 2,213 | 0.90 | 669 | 245 | Primary strategy; strongest bridge |
| **Device Name** | 63 | 0.80 | 59 | 42 | Exact device name found in ticket text |
| **IP Address** | 38 | 0.70 | 37 | 36 | IP matched between events and tickets |
| **TOTAL** | **2,314** | **0.89 avg** | **704** | **277** | |

---

## 3. Data Distribution

### Event Types (Top 10)

| Event Type | Count | Severity |
|-----------|-------|----------|
| Interface Up | 15,987 | Info |
| Interface Down | 15,638 | Warning |
| Node Down | 15,439 | Critical |
| Node Up | 14,371 | Info |
| EventType-5000 | 10,644 | Critical |
| EventType-51 | 10,516 | Warning |
| EventType-58 | 8,288 | Warning |
| EventType-5001 | 8,124 | Critical |
| EventType-529 | 6,368 | Warning |
| EventType-524 | 2,526 | Warning |

### Ticket Types and States

| Type | Count | | State | Count |
|------|-------|--|-------|-------|
| INC | 319 | | Closed | 197 |
| RITM | 68 | | Closed Complete | 83 |
| TASK | 52 | | In Progress | 48 |
| CHG | 3 | | On Hold | 48 |
| | | | Resolved | 37 |

### Top 5 Most Problematic Devices

| Device | Total Events | Node Down | Related Tickets |
|--------|-------------|-----------|----------------|
| 0001_Chantilly_VA_2960XR_X4-40 | 10 | 224 | 112 |
| 0055-AP196-Z2_OD | 785 | 158 | 0 |
| 3728-Santa-Clara-CA-N2248-X1-30 | 2,342 | 157 | 0 |
| 3724-Concord-CA-2248-X1-30 | 2,128 | 146 | 0 |
| 3529-Concord-NC-3248PXE-X1-MDF-40 | 2,009 | 132 | 0 |

**WARNING:** Several highly problematic devices (158+ Node Down events) have zero linked tickets.

---

## 4. Orphan Records

| Category | Count | Notes |
|----------|-------|-------|
| Events without device mapping | 26,365 (19.6%) | Events from NodeID=0 or NULL devices |
| Tickets without device links | 165 (37.3%) | Tickets without recognizable device/site references |

---

## 5. Recommendations

### Immediate Actions (Escalate to Data Team)

1. **Request full EventTime with dates** - The [DEVICE_ID] replacement destroyed the date portion.
2. **Request opened_by / assigned_to data** - Currently all NULL.
3. **Clarify EventType codes** - Types 51, 52, 58, 524, 529, 5000, 5001, 6808 need human-readable names.

### Database Improvements (Next Iteration)

4. **Expand ticket data** - 442 tickets for 6,583 devices is thin. Request 6-12 months of history.
5. **Add fuzzy matching** - Some device names have slight variations between systems.
6. **Add temporal correlation** - Once dates are available, match events to tickets by time proximity.

### For Backend Team

7. Use the `queries.sql` file for all API query templates.
8. The `device_ticket_map` table is the core bridge - always JOIN through it.
9. Confidence scores (0.7-0.9) can be used to rank results for LLM context.
