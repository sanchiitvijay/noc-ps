-- ============================================================================
-- TICKET HISTORY QUERIES — Copy-paste these into DB Browser "Execute SQL" tab
-- ============================================================================


-- ============================================================================
-- QUERY 1: Get full ticket history for a SPECIFIC DEVICE NAME
-- ============================================================================
-- Change the device name in the WHERE clause to any device you want
-- Example: '8395-Erlanger-KY-N2248ON-X1-40'

SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    t.ticket_number,
    t.ticket_type,
    t.state,
    t.short_description    AS issue,
    t.work_notes           AS resolution_steps,
    t.created_on           AS ticket_opened,
    t.closed_at            AS ticket_closed,
    m.match_type           AS how_matched,
    m.confidence
FROM device_ticket_map m
JOIN devices d    ON d.device_id = m.device_id
JOIN sn_tickets t ON t.ticket_id = m.ticket_id
WHERE d.device_name = '8395-Erlanger-KY-N2248ON-X1-40'
ORDER BY m.confidence DESC, t.created_on DESC;


-- ============================================================================
-- QUERY 2: Get full ticket history for a SITE CODE (FEI number)
-- ============================================================================
-- This finds ALL devices at that site and ALL their tickets
-- Change the site_code to: '0001', '8395', '0038', '3123', '2816' etc.

SELECT 
    d.device_name,
    d.ip_address,
    d.machine_type,
    t.ticket_number,
    t.ticket_type,
    t.state,
    t.short_description    AS issue,
    t.work_notes           AS resolution_steps,
    t.created_on           AS ticket_opened,
    t.closed_at            AS ticket_closed,
    m.match_type           AS how_matched,
    m.confidence
FROM device_ticket_map m
JOIN devices d    ON d.device_id = m.device_id
JOIN sn_tickets t ON t.ticket_id = m.ticket_id
WHERE d.site_code = '8395'
ORDER BY t.created_on DESC;


-- ============================================================================
-- QUERY 3: Get ticket history for a specific ERROR TYPE on a device
-- ============================================================================
-- Error types: 'Node Down', 'Interface Down', 'Interface Up', 
--              'Node Up', 'Interface Status Changed'
-- This shows: "Device X had Node Down errors, and here are the related tickets"

SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    e.event_type_name      AS error_type,
    COUNT(e.event_id)      AS times_this_error_occurred,
    t.ticket_number,
    t.state,
    t.short_description    AS ticket_issue,
    t.work_notes           AS what_fixed_it,
    t.created_on           AS ticket_opened,
    t.closed_at            AS ticket_closed
FROM devices d
JOIN event_logs e         ON e.device_id = d.device_id
JOIN device_ticket_map m  ON m.device_id = d.device_id
JOIN sn_tickets t         ON t.ticket_id = m.ticket_id
WHERE d.device_name LIKE '%8395-Erlanger%'
  AND e.event_type_name = 'Node Down'
GROUP BY t.ticket_id
ORDER BY t.created_on DESC;


-- ============================================================================
-- QUERY 4: Search by PARTIAL device name (don't know the full name)
-- ============================================================================
-- Use % as wildcard. Examples:
--   '%Erlanger%'    → finds anything with "Erlanger" in the name
--   '%Austin%'      → finds anything with "Austin"
--   '%0501%'        → finds anything with "0501"

SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    t.ticket_number,
    t.state,
    t.short_description    AS issue,
    t.work_notes           AS resolution_steps,
    t.created_on           AS ticket_opened,
    t.closed_at            AS ticket_closed
FROM device_ticket_map m
JOIN devices d    ON d.device_id = m.device_id
JOIN sn_tickets t ON t.ticket_id = m.ticket_id
WHERE d.device_name LIKE '%Erlanger%'
ORDER BY t.created_on DESC;


-- ============================================================================
-- QUERY 5: Get ONLY resolved tickets with fixes (what actually worked)
-- ============================================================================
-- This is what the LLM would use — past fixes for similar devices

SELECT 
    d.device_name,
    d.ip_address,
    d.site_code,
    d.machine_type,
    t.ticket_number,
    t.short_description    AS issue,
    t.work_notes           AS what_fixed_it,
    t.created_on           AS ticket_opened,
    t.closed_at            AS ticket_closed
FROM device_ticket_map m
JOIN devices d    ON d.device_id = m.device_id
JOIN sn_tickets t ON t.ticket_id = m.ticket_id
WHERE d.site_code = '0001'
  AND t.state IN ('Closed', 'Resolved', 'Closed Complete')
  AND t.work_notes IS NOT NULL
ORDER BY m.confidence DESC, t.closed_at DESC;


-- ============================================================================
-- QUERY 6: Full device profile — events + tickets combined
-- ============================================================================
-- The "everything about this device" query
-- Shows error history AND ticket history together

SELECT 
    '--- DEVICE INFO ---'   AS section,
    d.device_name           AS detail_1,
    d.ip_address            AS detail_2,
    d.machine_type          AS detail_3,
    d.vendor                AS detail_4,
    d.site_code             AS detail_5,
    ''                      AS detail_6
FROM devices d
WHERE d.device_name LIKE '%8395-Erlanger%'
LIMIT 1;

-- Then run this separately for event history:
SELECT 
    e.event_type_name       AS error_type,
    COUNT(*)                AS times_occurred
FROM event_logs e
JOIN devices d ON d.device_id = e.device_id
WHERE d.site_code = '8395'
GROUP BY e.event_type_name
ORDER BY times_occurred DESC;

-- Then run this for ticket history:
SELECT 
    t.ticket_number,
    t.state,
    t.short_description     AS issue,
    t.work_notes            AS resolution,
    t.created_on,
    t.closed_at
FROM device_ticket_map m
JOIN devices d    ON d.device_id = m.device_id
JOIN sn_tickets t ON t.ticket_id = m.ticket_id
WHERE d.site_code = '8395'
ORDER BY t.created_on DESC;


-- ============================================================================
-- QUERY 7: Specific Site + Specific Error Occurrence Count + Linked Tickets
-- ============================================================================
-- Answers: "How many times did 'Node Down' happen at site '8395', and what tickets exist for this site?"
--
-- Change these two values in the WHERE clauses:
--   1. d.site_code = '8395'          <-- Change site code here
--   2. e.event_type_name = 'Node Down' <-- Change error type here

WITH site_error_stats AS (
    -- Step 1: Count how many times this specific error occurred at this specific site
    SELECT 
        d.site_code,
        e.event_type_name AS error_type,
        COUNT(e.event_id) AS times_error_occurred_at_site
    FROM devices d
    JOIN event_logs e ON e.device_id = d.device_id
    WHERE d.site_code = '8395'
      AND e.event_type_name = 'Node Down'
    GROUP BY d.site_code, e.event_type_name
)
-- Step 2: Fetch tickets linked to devices at this site, alongside the error count
SELECT 
    d.site_code,
    ses.error_type,
    ses.times_error_occurred_at_site,
    t.ticket_number,
    t.state AS ticket_state,
    t.short_description AS ticket_issue,
    GROUP_CONCAT(DISTINCT d.device_name) AS devices_at_this_site,
    t.work_notes AS resolution_steps,
    t.created_on AS ticket_opened,
    t.closed_at AS ticket_closed
FROM devices d
JOIN site_error_stats ses ON ses.site_code = d.site_code
JOIN device_ticket_map m  ON m.device_id = d.device_id
JOIN sn_tickets t         ON t.ticket_id = m.ticket_id
WHERE d.site_code = '8395'
GROUP BY t.ticket_id
ORDER BY t.created_on DESC;

