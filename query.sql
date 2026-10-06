-- ============================================================================
-- NOC AUTOMATION — STANDARD QUERY TEMPLATE (For Backend Integration)
-- ============================================================================
--
-- PURPOSE:
--   Single parameterized query that accepts any combination of inputs
--   and returns a standardized output of ticket + event + device data.
--
-- HOW IT WORKS:
--   Pass NULL for any input you don't have. The query automatically
--   skips NULL filters, so you can use 1 input or all 6 at once.
--
-- ============================================================================
--
-- INPUTS (pass NULL for unused filters):
--   :ip_address     — e.g. '10.159.83.95'       or NULL
--   :device_name    — e.g. '%Erlanger%'          or NULL  (supports LIKE wildcards)
--   :device_type    — e.g. '%Cisco%'             or NULL  (supports LIKE wildcards)
--   :event_name     — e.g. 'Node Down'           or NULL  (exact match)
--   :device_id      — e.g. 5457                  or NULL  (exact match)
--   :error_message  — e.g. '%unreachable%'       or NULL  (supports LIKE wildcards)
--
-- OUTPUTS (per row):
--   ticket_number, ticket_type, state, created_on, updated_on,
--   short_description, description, work_notes,
--   severity, frequency,
--   device_type, device_name, ip_address, event_time, device_id, message
--
-- ============================================================================


SELECT
    -- Ticket fields
    t.ticket_number,
    t.ticket_type,
    t.state,
    t.created_on,
    t.updated_on,
    t.short_description,
    t.description,
    t.work_notes,

    -- Severity: P1 (most severe) to P4 (least severe)
    CASE
        WHEN e.event_type_name IN ('Node Down', 'EventType-5000', 'EventType-5001')  THEN 'P1'
        WHEN e.event_type_name IN ('Interface Down', 'Interface Status Changed')      THEN 'P2'
        WHEN e.event_type_name IN ('Node Up', 'Interface Up')                         THEN 'P3'
        ELSE 'P4'
    END AS severity,

    -- Frequency: total matching events for this device
    COUNT(e.event_id) AS frequency,

    -- Device + Event fields
    d.machine_type AS device_type,
    d.device_name,
    d.ip_address,
    e.event_time,
    d.device_id,
    e.message

FROM sn_tickets t
JOIN device_ticket_map m ON m.ticket_id = t.ticket_id
JOIN devices d           ON d.device_id = m.device_id
JOIN event_logs e        ON e.device_id = d.device_id

WHERE 1=1
  AND (:ip_address    IS NULL OR d.ip_address      = :ip_address)
  AND (:device_name   IS NULL OR d.device_name     LIKE :device_name)
  AND (:device_type   IS NULL OR d.machine_type    LIKE :device_type)
  AND (:event_name    IS NULL OR e.event_type_name = :event_name)
  AND (:device_id     IS NULL OR d.device_id       = :device_id)
  AND (:error_message IS NULL OR e.message         LIKE :error_message)

GROUP BY t.ticket_id, d.device_id
ORDER BY t.created_on DESC
LIMIT 50;