-- ============================================================================
-- NOC AUTOMATION - DATABASE VALIDATION QUERIES
-- Run these after ETL to verify data integrity
-- ============================================================================

-- 1. Table row counts
SELECT 'devices' AS table_name, COUNT(*) AS row_count FROM devices
UNION ALL SELECT 'event_logs', COUNT(*) FROM event_logs
UNION ALL SELECT 'sn_tickets', COUNT(*) FROM sn_tickets
UNION ALL SELECT 'device_ticket_map', COUNT(*) FROM device_ticket_map
UNION ALL SELECT 'event_type_lookup', COUNT(*) FROM event_type_lookup;

-- 2. Cross-reference quality
SELECT 
    match_type,
    COUNT(*) AS link_count,
    ROUND(AVG(confidence), 2) AS avg_confidence,
    COUNT(DISTINCT device_id) AS unique_devices,
    COUNT(DISTINCT ticket_id) AS unique_tickets
FROM device_ticket_map
GROUP BY match_type;

-- 3. Device coverage (how many devices have at least 1 ticket?)
SELECT 
    ROUND(100.0 * COUNT(DISTINCT m.device_id) / (SELECT COUNT(*) FROM devices), 1) 
        AS pct_devices_with_tickets
FROM device_ticket_map m;

-- 4. Top 10 most problematic devices
SELECT * FROM vw_hot_devices LIMIT 10;

-- 5. Ticket state distribution
SELECT * FROM vw_ticket_stats;

-- 6. Sample cross-reference (verify quality)
SELECT 
    d.device_name,
    d.ip_address,
    t.ticket_number,
    t.short_description,
    m.match_type,
    m.match_value,
    m.confidence
FROM device_ticket_map m
JOIN devices d ON d.device_id = m.device_id
JOIN sn_tickets t ON t.ticket_id = m.ticket_id
ORDER BY m.confidence DESC
LIMIT 20;

-- 7. Events without device mapping
SELECT COUNT(*) AS orphan_events 
FROM event_logs 
WHERE device_id IS NULL;

-- 8. Devices with most events (sanity check)
SELECT 
    d.device_name, 
    d.ip_address,
    COUNT(e.event_id) AS event_count
FROM devices d
JOIN event_logs e ON e.device_id = d.device_id
GROUP BY d.device_id
ORDER BY event_count DESC
LIMIT 10;
