-- ============================================================================
-- NOC AUTOMATION - QUERY TEMPLATES
-- For Backend API Consumption
-- ============================================================================

-- ============================================================================
-- Q1: GET HISTORICAL TICKETS FOR A DEVICE (Core NOC Alert Query)
-- ============================================================================
-- When SolarWinds fires an alert for a device, use this query to fetch
-- all historically related ServiceNow tickets.
-- Params: :device_name (from alert), :ip_address (from alert)

SELECT 
    t.ticket_number,
    t.ticket_type,
    t.state,
    t.short_description,
    t.work_notes,
    t.created_on,
    t.closed_at,
    m.match_type,
    m.match_value,
    m.confidence
FROM sn_tickets t
JOIN device_ticket_map m ON t.ticket_id = m.ticket_id
JOIN devices d ON d.device_id = m.device_id
WHERE d.device_name = :device_name 
   OR d.ip_address = :ip_address
ORDER BY m.confidence DESC, t.created_on DESC;


-- ============================================================================
-- Q2: BUILD LLM CONTEXT PACKAGE FOR A DEVICE
-- ============================================================================
-- Comprehensive context for the LLM to generate troubleshooting suggestions.
-- Returns: device info + recent events + related resolved tickets
-- Params: :device_name

-- Part A: Device Info
SELECT 
    d.device_id,
    d.device_name,
    d.ip_address,
    d.site_code,
    d.site_name,
    d.machine_type,
    d.vendor,
    d.location
FROM devices d
WHERE d.device_name = :device_name;

-- Part B: Recent Events for this device
SELECT 
    e.event_id,
    e.event_time,
    e.event_type_name,
    e.message,
    e.current_status,
    e.raw_detail
FROM event_logs e
JOIN devices d ON d.device_id = e.device_id
WHERE d.device_name = :device_name
ORDER BY e.event_id DESC
LIMIT 50;

-- Part C: Related Resolved Tickets (for past fix patterns)
SELECT 
    t.ticket_number,
    t.ticket_type,
    t.state,
    t.short_description,
    t.description,
    t.work_notes,
    t.created_on,
    t.closed_at,
    m.match_type,
    m.confidence
FROM sn_tickets t
JOIN device_ticket_map m ON t.ticket_id = m.ticket_id
JOIN devices d ON d.device_id = m.device_id
WHERE d.device_name = :device_name
  AND t.state IN ('Closed', 'Resolved', 'Closed Complete')
ORDER BY m.confidence DESC, t.closed_at DESC
LIMIT 20;


-- ============================================================================
-- Q3: DEVICE ALERT FREQUENCY (Hot Spots / Dashboard)
-- ============================================================================
-- Identify the most problematic devices for NOC dashboard

SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    d.vendor,
    COUNT(DISTINCT e.event_id) AS total_events,
    SUM(CASE WHEN e.event_type_name = 'Node Down' THEN 1 ELSE 0 END) AS node_down_count,
    SUM(CASE WHEN e.event_type_name = 'Interface Down' THEN 1 ELSE 0 END) AS iface_down_count,
    COUNT(DISTINCT m.ticket_id) AS related_ticket_count
FROM devices d
LEFT JOIN event_logs e ON e.device_id = d.device_id
LEFT JOIN device_ticket_map m ON m.device_id = d.device_id
GROUP BY d.device_id
HAVING node_down_count > 0
ORDER BY node_down_count DESC
LIMIT 50;


-- ============================================================================
-- Q4: RESOLUTION PATTERN ANALYSIS
-- ============================================================================
-- What fixes have worked for devices with the same machine_type?
-- Params: :machine_type

SELECT 
    t.ticket_number,
    t.short_description,
    t.work_notes,
    t.state,
    d.device_name,
    d.machine_type,
    d.vendor,
    t.created_on,
    t.closed_at
FROM sn_tickets t
JOIN device_ticket_map m ON t.ticket_id = m.ticket_id
JOIN devices d ON d.device_id = m.device_id
WHERE t.state IN ('Closed', 'Resolved', 'Closed Complete')
  AND d.machine_type = :machine_type
ORDER BY t.closed_at DESC;


-- ============================================================================
-- Q5: SIMILAR DEVICE LOOKUP
-- ============================================================================
-- Find other devices at the same site (for blast radius analysis)
-- Params: :site_code

SELECT 
    d.device_name,
    d.ip_address,
    d.machine_type,
    d.vendor,
    COUNT(DISTINCT e.event_id) AS event_count,
    SUM(CASE WHEN e.event_type_name = 'Node Down' THEN 1 ELSE 0 END) AS down_events
FROM devices d
LEFT JOIN event_logs e ON e.device_id = d.device_id
WHERE d.site_code = :site_code
GROUP BY d.device_id
ORDER BY down_events DESC;


-- ============================================================================
-- Q6: TICKET SEARCH BY KEYWORD
-- ============================================================================
-- Search tickets by keyword in description/work_notes
-- Params: :keyword

SELECT 
    t.ticket_number,
    t.state,
    t.short_description,
    t.work_notes,
    t.created_on,
    t.closed_at
FROM sn_tickets t
WHERE t.short_description LIKE '%' || :keyword || '%'
   OR t.description LIKE '%' || :keyword || '%'
   OR t.work_notes LIKE '%' || :keyword || '%'
ORDER BY t.created_on DESC
LIMIT 25;


-- ============================================================================
-- Q7: EVENT TYPE DISTRIBUTION FOR A DEVICE
-- ============================================================================
-- Breakdown of event types for a specific device
-- Params: :device_name

SELECT 
    e.event_type_name,
    etl.severity,
    etl.category,
    COUNT(*) AS event_count
FROM event_logs e
JOIN devices d ON d.device_id = e.device_id
LEFT JOIN event_type_lookup etl ON etl.event_type_id = e.event_type_id
WHERE d.device_name = :device_name
GROUP BY e.event_type_name
ORDER BY event_count DESC;


-- ============================================================================
-- Q8: CROSS-REFERENCE QUALITY REPORT
-- ============================================================================
-- How many devices have ticket mappings? What's the coverage?

SELECT 
    'Total Devices' AS metric, COUNT(*) AS value FROM devices
UNION ALL
SELECT 
    'Devices with Tickets', COUNT(DISTINCT device_id) FROM device_ticket_map
UNION ALL
SELECT 
    'Total Tickets', COUNT(*) FROM sn_tickets
UNION ALL
SELECT 
    'Tickets Linked to Devices', COUNT(DISTINCT ticket_id) FROM device_ticket_map
UNION ALL
SELECT 
    'Total Cross-Ref Links', COUNT(*) FROM device_ticket_map
UNION ALL
SELECT 
    'Avg Confidence', ROUND(AVG(confidence), 2) FROM device_ticket_map;


-- ============================================================================
-- Q9: FIND DEVICE BY ALERT PARAMETERS
-- ============================================================================
-- Backend receives an alert with device name OR IP - find the device
-- Params: :search_term

SELECT 
    d.device_id,
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    d.vendor,
    d.location
FROM devices d
WHERE d.device_name LIKE '%' || :search_term || '%'
   OR d.ip_address = :search_term
   OR d.site_code = :search_term
LIMIT 10;


-- ============================================================================
-- Q10: FULL LLM PROMPT CONTEXT (Single Combined Query)
-- ============================================================================
-- One-shot query to build the full context for LLM prompt generation
-- Params: :device_name, :ip_address

SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    d.vendor,
    d.location,
    -- Event summary
    (SELECT COUNT(*) FROM event_logs e2 WHERE e2.device_id = d.device_id) AS total_events,
    (SELECT COUNT(*) FROM event_logs e3 WHERE e3.device_id = d.device_id AND e3.event_type_name = 'Node Down') AS total_node_down,
    -- Ticket info (aggregated)
    (SELECT GROUP_CONCAT(t2.ticket_number || ': ' || t2.short_description, ' | ')
     FROM sn_tickets t2
     JOIN device_ticket_map m2 ON t2.ticket_id = m2.ticket_id
     WHERE m2.device_id = d.device_id
     AND t2.state IN ('Closed', 'Resolved', 'Closed Complete')
    ) AS resolved_ticket_summary,
    -- Latest work notes from resolved tickets
    (SELECT t3.work_notes 
     FROM sn_tickets t3
     JOIN device_ticket_map m3 ON t3.ticket_id = m3.ticket_id
     WHERE m3.device_id = d.device_id
     AND t3.state IN ('Closed', 'Resolved', 'Closed Complete')
     AND t3.work_notes IS NOT NULL
     ORDER BY m3.confidence DESC
     LIMIT 1
    ) AS latest_resolution_notes
FROM devices d
WHERE d.device_name = :device_name 
   OR d.ip_address = :ip_address
LIMIT 1;
