# Postman Dummy Requests — NOC Automation API

This file contains mock requests for the NOC Automation backend. You can copy the URL, HTTP Method, Request Body, and Headers directly into Postman to test the API locally.

**Base URL:** `http://localhost:8000`

---

## 1. Authentication (No Token Required)

### 1.1 Signup
Create a new Admin or Analyst user.
- **Method:** `POST`
- **URL:** `http://localhost:8000/auth/signup`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "username": "admin",
  "email": "admin@example.com",
  "password": "adminpassword123!",
  "role": "admin"
}
```
- **Expected Response (201 Created):**
```json
{
  "success": true,
  "message": "Account created successfully",
  "data": {
    "user": {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "role": "admin",
      "is_active": 1,
      "created_at": "2026-10-05 14:00:00"
    },
    "tokens": {
      "access_token": "eyJhbGciOi...",
      "refresh_token": "eyJhbGciOi...",
      "token_type": "bearer",
      "expires_in": 1800
    }
  }
}
```

### 1.2 Login
Obtain your JWT tokens. **Copy the `access_token` from the response** to use in all subsequent requests.
- **Method:** `POST`
- **URL:** `http://localhost:8000/auth/login`
- **Headers:** `Content-Type: application/json`
- **Request Body:**
```json
{
  "username": "admin",
  "password": "adminpassword123!"
}
```
- **Expected Response (200 OK):** (Same structure as Signup response)

---

## 🛑 IMPORTANT: Setting up Authorization
For all requests below, you must include the access token in your Postman headers:
- Go to the **Authorization** tab in Postman.
- Select **Type:** `Bearer Token`.
- Paste the `access_token` string into the **Token** field.

---

## 2. NOC Analyst Dashboard

### 2.1 Get Global Metrics
Fetches widget data for the NOC dashboard.
- **Method:** `GET`
- **URL:** `http://localhost:8000/get-metrics`
- **Headers:** `Authorization: Bearer <your_token>`
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Metrics retrieved successfully",
  "data": {
    "total_devices": 6583,
    "total_events_all_time": 134385,
    "events_by_severity": {
      "P1": 412,
      "P2": 19020,
      "P3": 114953
    },
    "events_by_category": {
      "connectivity": 240,
      "interface": 1024,
      "performance": 401,
      "wireless": 204
    },
    "top_alerting_devices": [
      {
        "device_name": "0001-AP184-Z3",
        "ip_address": "10.142.44.184",
        "event_count": 15
      }
    ],
    "ticket_stats": {
      "total_tickets": 442,
      "by_state": { "Pending": 120, "Closed": 300, "Active": 22 },
      "by_type": { "INC": 300, "RITM": 142 }
    }
  }
}
```

### 2.2 Get Event Logs
Fetches a paginated list of network events.
- **Method:** `GET`
- **URL:** `http://localhost:8000/get-logs?page=1&page_size=5&severity=P1`
- **Headers:** `Authorization: Bearer <your_token>`
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Logs retrieved successfully",
  "data": [
    {
      "event_id": 123236587,
      "event_time": "02:25:17.687",
      "event_type_name": "Node Down",
      "severity": "P1",
      "message": "SW-CORE-02 is down. 100% packet loss.",
      "device_id": 42,
      "device_name": "SW-CORE-02"
    }
  ],
  "meta": {
    "total": 412,
    "page": 1,
    "page_size": 5
  }
}
```

### 2.3 Simulate Event Logs (Demo / Streaming Simulation)
Returns randomly sampled real event logs interleaved with synthetic event logs for frontend demo streaming.
- **Method:** `GET`
- **URL:** `http://localhost:8000/simulate/logs?count=10&synthetic_ratio=0.2`
- **Headers:** `Authorization: Bearer <your_token>`
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "OK",
  "data": [
    {
      "event_id": 123236587,
      "event_time": "14:22:05.123",
      "event_type_name": "Node Down",
      "severity": "P1",
      "category": "connectivity",
      "message": "SW-CORE-02 is down. 100% packet loss.",
      "device_id": 42,
      "device_name": "SW-CORE-02",
      "ip_address": "10.10.10.5",
      "current_status": 0,
      "raw_detail": null,
      "simulated": false
    },
    {
      "event_id": 900001,
      "event_time": "14:15:32.000",
      "event_type_name": "High CPU",
      "severity": "P2",
      "category": "performance",
      "message": "High CPU utilization: 92% for 5 minutes",
      "device_id": 105,
      "device_name": "SIM-DEVICE-012",
      "ip_address": "10.45.12.3",
      "current_status": 1,
      "raw_detail": null,
      "simulated": true
    }
  ],
  "meta": {
    "total_returned": 2,
    "real_count": 1,
    "synthetic_count": 1
  }
}
```

### 2.4 Automated Error Analysis Panel (LLM Powered)
Runs diagnostic checks, looks up past ServiceNow tickets, and queries Gemini for a solution.
- **Method:** `GET`
- **URL:** `http://localhost:8000/error-info?device_id=2&event_type_id=1`
- **Headers:** `Authorization: Bearer <your_token>`
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Error info generated successfully",
  "data": {
    "device": {
      "device_id": 2,
      "device_name": "0001-AP184-Z3",
      "ip_address": "10.142.44.184",
      "machine_type": "Cisco Catalyst 29xxStack"
    },
    "event_type": {
      "event_type_name": "Node Down",
      "severity": "P1",
      "category": "connectivity"
    },
    "historical_info": {
      "total_incidents_6m": 2,
      "related_tickets": [
        {
          "ticket_number": "INC001234",
          "state": "Closed",
          "short_description": "AP184-Z3 offline",
          "work_notes": "Rebooted access point. Service restored."
        }
      ]
    },
    "preliminary_checks": {
      "ping": {
        "host": "10.142.44.184",
        "reachable": false,
        "packet_loss_pct": 100
      },
      "traceroute": {
        "host": "10.142.44.184",
        "completed": false,
        "error": "Failed at Hop 3 (192.168.100.1)"
      }
    },
    "suggested_solution": {
      "generated_by": "gemini",
      "confidence": "high",
      "hypothesis": "Access Point hardware lockup or PoE power loss from upstream switch.",
      "recommended_steps": [
        "1. Check PoE power status on upstream switch port.",
        "2. Perform a hard bounce of the switch port.",
        "3. Dispatch field technician if unrecoverable."
      ]
    }
  }
}
```

---

## 3. Manual Internal Diagnostics

### 3.1 Ping
- **Method:** `POST`
- **URL:** `http://localhost:8000/internal/ping`
- **Headers:** `Authorization: Bearer <your_token>`, `Content-Type: application/json`
- **Request Body:**
```json
{
  "host": "10.142.44.184",
  "count": 4
}
```
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Ping diagnostic completed",
  "data": {
    "host": "10.142.44.184",
    "reachable": false,
    "packet_loss_pct": 100,
    "avg_rtt_ms": null
  }
}
```

### 3.2 Traceroute
- **Method:** `POST`
- **URL:** `http://localhost:8000/internal/traceroute`
- **Headers:** `Authorization: Bearer <your_token>`, `Content-Type: application/json`
- **Request Body:**
```json
{
  "host": "8.8.8.8"
}
```
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Traceroute completed",
  "data": {
    "host": "8.8.8.8",
    "completed": true,
    "hops": [
      "1  192.168.1.1  1.123 ms",
      "2  10.0.0.1  5.432 ms",
      "3  8.8.8.8  15.123 ms"
    ]
  }
}
```

### 3.3 NSLookup
- **Method:** `POST`
- **URL:** `http://localhost:8000/internal/nslookup`
- **Headers:** `Authorization: Bearer <your_token>`, `Content-Type: application/json`
- **Request Body:**
```json
{
  "host": "google.com"
}
```
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "NSLookup completed",
  "data": {
    "host": "google.com",
    "addresses": ["142.250.190.46"],
    "reverse_lookup": "lax17s44-in-f14.1e100.net"
  }
}
```

---

## 4. Admin Operations

*(Requires token with `role: admin`)*

### 4.1 Ingest Excel / CSV File
*Note: In Postman, switch body type to `form-data` for this request.*
- **Method:** `POST`
- **URL:** `http://localhost:8000/admin/ingest-excel`
- **Headers:** `Authorization: Bearer <your_token>` (Do NOT manually set Content-Type, let Postman set it to `multipart/form-data`)
- **Request Body (form-data):**
  - **Key:** `file` (Change type from Text to **File**)
  - **Value:** [Select your CSV file]
- **Expected Response (202 Accepted):**
```json
{
  "success": true,
  "message": "File accepted for ingestion. Processing in background.",
  "data": {
    "job_id": 1,
    "filename": "30_Days_EventTypeName_device_name_ANONYMIZED.csv"
  }
}
```

### 4.2 Get Activity Log
- **Method:** `GET`
- **URL:** `http://localhost:8000/admin/activity-log?page=1&page_size=10`
- **Headers:** `Authorization: Bearer <your_token>`
- **Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Activity logs retrieved",
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "username": "admin",
      "action": "GET /get-metrics",
      "ip_address": "127.0.0.1",
      "response_status": 200,
      "created_at": "2026-10-05 14:15:00"
    }
  ],
  "meta": {
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```
