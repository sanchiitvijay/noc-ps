-- ============================================================================
-- NOC AUTOMATION DATABASE SCHEMA
-- Project: Automated NOC Assistant
-- Role: Database Engineer
-- Created: October 4, 2026
-- Database: SQLite (noc_automation.db)
-- ============================================================================

-- ============================================================================
-- 1. REFERENCE / LOOKUP TABLES
-- ============================================================================

-- Event Type Reference Table
CREATE TABLE IF NOT EXISTS event_type_lookup (
    event_type_id   INTEGER PRIMARY KEY,
    event_type_name TEXT    NOT NULL,
    severity        TEXT    CHECK(severity IN ('Critical','Warning','Info','Unknown')),
    category        TEXT    CHECK(category IN ('connectivity','interface','performance','wireless','power','other'))
);

-- Seed event type lookup with known types from the data
INSERT OR IGNORE INTO event_type_lookup (event_type_id, event_type_name, severity, category) VALUES
    (1,    'Node Down',                'Critical',  'connectivity'),
    (5,    'Node Up',                  'Info',      'connectivity'),
    (10,   'Interface Down',           'Warning',   'interface'),
    (11,   'Interface Up',             'Info',      'interface'),
    (14,   'EventType-14',            'Warning',   'other'),
    (19,   'Interface Status Changed', 'Warning',   'interface'),
    (51,   'EventType-51',            'Warning',   'other'),
    (52,   'EventType-52',            'Warning',   'other'),
    (58,   'EventType-58',            'Warning',   'other'),
    (524,  'EventType-524',           'Warning',   'other'),
    (529,  'EventType-529',           'Warning',   'performance'),
    (604,  'EventType-604',           'Warning',   'wireless'),
    (3805, 'EventType-3805',          'Warning',   'performance'),
    (5000, 'EventType-5000',          'Critical',  'connectivity'),
    (5001, 'EventType-5001',          'Critical',  'connectivity'),
    (6808, 'EventType-6808',          'Warning',   'other');

-- ============================================================================
-- 2. CORE TABLES
-- ============================================================================

-- Device Master Registry
-- Unique network devices extracted from event logs
CREATE TABLE IF NOT EXISTS devices (
    device_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id         INTEGER,
    device_name     TEXT    NOT NULL,
    ip_address      TEXT,
    site_code       TEXT,              -- Extracted FEI/site number (e.g., '0501')
    site_name       TEXT,              -- Extracted location name (e.g., 'Lakewood-NJ')
    machine_type    TEXT,
    vendor          TEXT,
    location        TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(device_name, ip_address)
);

-- Network Event Logs (SolarWinds Alerts)
-- 30 days of real-time network events
CREATE TABLE IF NOT EXISTS event_logs (
    event_id          INTEGER PRIMARY KEY,
    event_time        TEXT,              -- Time portion only (HH:MM:SS.mmm) - date unavailable
    event_type_id     INTEGER,
    event_type_name   TEXT,              -- Denormalized for query performance
    message           TEXT,
    device_id         INTEGER,
    current_status    INTEGER,
    raw_detail        TEXT,              -- Additional detail from source data
    
    FOREIGN KEY (device_id)      REFERENCES devices(device_id),
    FOREIGN KEY (event_type_id)  REFERENCES event_type_lookup(event_type_id)
);

-- ServiceNow Tickets
-- NOC team incident/request/task/change records
CREATE TABLE IF NOT EXISTS sn_tickets (
    ticket_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number          TEXT    UNIQUE NOT NULL,
    ticket_type            TEXT    CHECK(ticket_type IN ('INC','RITM','TASK','CHG')),
    state                  TEXT,
    created_on             TEXT,        -- Original date string (MM-DD-YYYY HH:MM)
    updated_on             TEXT,
    closed_at              TEXT,
    assignment_group       TEXT,
    short_description      TEXT,
    description            TEXT,
    work_notes             TEXT,
    extracted_site_codes   TEXT,        -- JSON array of FEI codes found in text
    extracted_ips          TEXT,        -- JSON array of IPs found in text
    extracted_device_names TEXT         -- JSON array of device names found in text
);

-- Device <-> Ticket Cross-Reference Bridge
-- Links devices to related ServiceNow tickets via multiple matching strategies
CREATE TABLE IF NOT EXISTS device_ticket_map (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   INTEGER NOT NULL,
    ticket_id   INTEGER NOT NULL,
    match_type  TEXT    NOT NULL CHECK(match_type IN ('site_code','device_name','ip_address')),
    match_value TEXT,
    confidence  REAL    DEFAULT 0.5 CHECK(confidence >= 0.0 AND confidence <= 1.0),

    FOREIGN KEY (device_id) REFERENCES devices(device_id),
    FOREIGN KEY (ticket_id) REFERENCES sn_tickets(ticket_id),
    UNIQUE(device_id, ticket_id, match_type)
);

-- ============================================================================
-- 3. INDEXES (Optimized for NOC query patterns)
-- ============================================================================

-- Device lookups (triggered by alert events)
CREATE INDEX IF NOT EXISTS idx_devices_name       ON devices(device_name);
CREATE INDEX IF NOT EXISTS idx_devices_ip         ON devices(ip_address);
CREATE INDEX IF NOT EXISTS idx_devices_site_code  ON devices(site_code);
CREATE INDEX IF NOT EXISTS idx_devices_node_id    ON devices(node_id);

-- Event log queries (historical event retrieval)
CREATE INDEX IF NOT EXISTS idx_events_device_id   ON event_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_events_type        ON event_logs(event_type_id);
CREATE INDEX IF NOT EXISTS idx_events_time        ON event_logs(event_time);
CREATE INDEX IF NOT EXISTS idx_events_status      ON event_logs(current_status);

-- Ticket queries (historical ticket retrieval)
CREATE INDEX IF NOT EXISTS idx_tickets_number     ON sn_tickets(ticket_number);
CREATE INDEX IF NOT EXISTS idx_tickets_state      ON sn_tickets(state);
CREATE INDEX IF NOT EXISTS idx_tickets_created    ON sn_tickets(created_on);

-- Cross-reference queries (the core bridge)
CREATE INDEX IF NOT EXISTS idx_dtmap_device       ON device_ticket_map(device_id);
CREATE INDEX IF NOT EXISTS idx_dtmap_ticket       ON device_ticket_map(ticket_id);
CREATE INDEX IF NOT EXISTS idx_dtmap_confidence   ON device_ticket_map(confidence DESC);

-- ============================================================================
-- 4. VIEWS (Pre-built queries for common patterns)
-- ============================================================================

-- View: Device with ticket count summary
CREATE VIEW IF NOT EXISTS vw_device_summary AS
SELECT 
    d.device_id,
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    d.vendor,
    COUNT(DISTINCT e.event_id)  AS total_events,
    SUM(CASE WHEN e.event_type_name = 'Node Down' THEN 1 ELSE 0 END) AS node_down_count,
    SUM(CASE WHEN e.event_type_name = 'Interface Down' THEN 1 ELSE 0 END) AS interface_down_count,
    COUNT(DISTINCT m.ticket_id) AS related_ticket_count
FROM devices d
LEFT JOIN event_logs e ON e.device_id = d.device_id
LEFT JOIN device_ticket_map m ON m.device_id = d.device_id
GROUP BY d.device_id;

-- View: Resolved tickets with resolution details (for LLM context)
CREATE VIEW IF NOT EXISTS vw_resolved_tickets AS
SELECT 
    t.ticket_number,
    t.ticket_type,
    t.short_description,
    t.description,
    t.work_notes,
    t.created_on,
    t.closed_at,
    t.extracted_site_codes,
    t.extracted_ips
FROM sn_tickets t
WHERE t.state IN ('Closed', 'Resolved', 'Closed Complete');

-- View: Device historical context (full picture for a device)
CREATE VIEW IF NOT EXISTS vw_device_history AS
SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    d.vendor,
    d.location,
    e.event_id,
    e.event_time,
    e.event_type_name,
    e.message,
    e.current_status,
    t.ticket_number,
    t.state         AS ticket_state,
    t.short_description AS ticket_title,
    t.work_notes    AS resolution_notes,
    m.match_type,
    m.confidence
FROM devices d
LEFT JOIN event_logs e        ON e.device_id = d.device_id
LEFT JOIN device_ticket_map m ON m.device_id = d.device_id
LEFT JOIN sn_tickets t        ON t.ticket_id = m.ticket_id;

-- View: Top problematic devices (NOC dashboard hot list)
CREATE VIEW IF NOT EXISTS vw_hot_devices AS
SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    COUNT(DISTINCT e.event_id) AS total_events,
    SUM(CASE WHEN e.event_type_name = 'Node Down' THEN 1 ELSE 0 END) AS critical_events,
    COUNT(DISTINCT m.ticket_id) AS ticket_count
FROM devices d
JOIN event_logs e ON e.device_id = d.device_id
LEFT JOIN device_ticket_map m ON m.device_id = d.device_id
GROUP BY d.device_id
HAVING critical_events > 0
ORDER BY critical_events DESC, total_events DESC;

-- View: Ticket type distribution
CREATE VIEW IF NOT EXISTS vw_ticket_stats AS
SELECT 
    ticket_type,
    state,
    COUNT(*) AS ticket_count,
    COUNT(closed_at) AS resolved_count
FROM sn_tickets
GROUP BY ticket_type, state
ORDER BY ticket_count DESC;
