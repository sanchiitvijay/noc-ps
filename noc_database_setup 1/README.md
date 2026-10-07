# NOC Automation Database - Complete Setup & Replication Guide

This guide gives you the **exact, zero-theory, step-by-step instructions** to replicate this entire database system on your work laptop from scratch.

---

## 1. What You Need on Your Work Laptop (Prerequisites)

### A. Python 3 (3.8 or higher)
1. Download from [python.org/downloads](https://www.python.org/downloads/) if not already installed.
2. **CRITICAL DURING INSTALL**: Check the box that says **"Add python.exe to PATH"**.
3. Verify by opening PowerShell or Command Prompt and running:
   ```powershell
   python --version
   ```

### B. Install Python Dependencies
Open PowerShell or Command Prompt and run:
```powershell
pip install pandas
```
*(Note: `sqlite3` is built into Python by default. No other installs are needed).*

### C. DB Browser for SQLite (Visual GUI Tool)
1. Download the installer or portable zip from: [sqlitebrowser.org/dl](https://sqlitebrowser.org/dl/)
   - Standard: `DB.Browser.for.SQLite-x64.msi`
   - No-install portable: `DB.Browser.for.SQLite-win64.zip`
2. Install or extract it.

---

## 2. File Structure

All files must sit together in the same directory:

```text
noc_automation/
│
├── 30_Days_EventTypeName_device_name_ANONYMIZED.csv  <- SolarWinds event logs (134K rows)
├── SN_Tickets_NOC_anonymized.csv                     <- ServiceNow tickets (442 rows)
│
├── schema.sql                                        <- Database schema (5 tables, 13 indexes, 5 views)
├── etl_pipeline.py                                   <- Automated Python ETL script
├── noc_automation.db                                 <- SQLite database file (pre-built)
│
├── ticket_history_queries.sql                        <- 7 practical NOC queries (ready to run)
├── queries.sql                                       <- 10 backend API query templates
├── validate_db.sql                                   <- SQL sanity check queries
├── data_quality_report.md                            <- Dataset anomalies and quality findings
└── README.md                                         <- This guide
```

---

## 3. Fast Path: Use the Pre-Built Database (30 Seconds)

If you copied `noc_automation.db` along with the files, you do NOT need to run the ETL script. The database is already built and ready:

1. Launch **DB Browser for SQLite**.
2. Click **Open Database** (top-left button or `Ctrl+O`).
3. Browse to your folder and select `noc_automation.db`.
4. Click on the **"Execute SQL"** tab.
5. Open `ticket_history_queries.sql` in Notepad or VS Code, copy any query, paste it into the editor, and click the blue **Play button ▶** (or press **F5**).

---

## 4. Full Rebuild Path: Run the Pipeline From Scratch

If you want to re-generate `noc_automation.db` from the raw CSVs on your work laptop:

### Step 1: Open PowerShell in the project folder
1. Open File Explorer to your project folder.
2. In the folder address bar at the top, type `powershell` and press **Enter**.

### Step 2: Delete any old database (optional)
```powershell
Remove-Item noc_automation.db -ErrorAction Ignore
```

### Step 3: Run the ETL Pipeline
```powershell
python etl_pipeline.py
```

### Expected Output in Terminal:
```text
============================================================
NOC Automation Database ETL Pipeline
============================================================

[1/5] Initializing Database Schema...
  Database: noc_automation.db
  Schema script: schema.sql
  Database initialized successfully.

[2/5] Ingesting SolarWinds Event Logs...
  Loaded 134,416 raw event records.
  Extracted 6,583 unique devices.
  Inserted 6,583 devices into database.
  Inserted 134,385 event records into database.

[3/5] Ingesting ServiceNow Tickets...
  Loaded 442 raw tickets.
  Enrichment stats:
    Tickets with FEI codes extracted: 297
    Tickets with IPs extracted: 166
    Tickets with device names extracted: 42
  Inserted 442 tickets into database.

[4/5] Building Cross-Reference Bridge (device_ticket_map)...
  Matched by site_code: 2,213 links (confidence=0.90)
  Matched by device_name: 63 links (confidence=0.80)
  Matched by ip_address: 38 links (confidence=0.70)
  Total cross-reference links created: 2,314
  Unique devices linked to tickets: 704
  Unique tickets linked to devices: 277

[5/5] Re-indexing and Optimizing...
  Rebuilding indexes...
  Running PRAGMA optimize...
  Database optimized.

ETL PIPELINE COMPLETED SUCCESSFULLY!
Final database size: 47.74 MB
```

---

## 5. Verify the Database

### Quick Verification from PowerShell:
Run this single command:
```powershell
python -c "import sqlite3; conn = sqlite3.connect('noc_automation.db'); c = conn.cursor(); print('Devices:', c.execute('SELECT COUNT(*) FROM devices').fetchone()[0]); print('Events:', c.execute('SELECT COUNT(*) FROM event_logs').fetchone()[0]); print('Tickets:', c.execute('SELECT COUNT(*) FROM sn_tickets').fetchone()[0]); print('Links:', c.execute('SELECT COUNT(*) FROM device_ticket_map').fetchone()[0])"
```

Expected counts:
- **Devices**: 6,583
- **Events**: 134,385
- **Tickets**: 442
- **Links**: 2,314

---

## 6. How to Run Ticket & Error Queries

Open `ticket_history_queries.sql` in DB Browser under the **"Execute SQL"** tab.

### Key Query: Error Count at Specific Site + Linked Tickets
To find how many times a specific error (e.g. `'Node Down'`) happened at a specific site (e.g. `'8395'`) and get the historical tickets with resolution notes:

```sql
WITH site_error_stats AS (
    SELECT 
        d.site_code,
        e.event_type_name AS error_type,
        COUNT(e.event_id) AS times_error_occurred_at_site
    FROM devices d
    JOIN event_logs e ON e.device_id = d.device_id
    WHERE d.site_code = '8395'              -- <-- CHANGE SITE CODE HERE
      AND e.event_type_name = 'Node Down'   -- <-- CHANGE ERROR TYPE HERE
    GROUP BY d.site_code, e.event_type_name
)
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
WHERE d.site_code = '8395'                  -- <-- CHANGE SITE CODE HERE
GROUP BY t.ticket_id
ORDER BY t.created_on DESC;
```

### Try These Other Test Sites:
- **Site `2800`** with error `'Interface Down'` (28 occurrences, Ticket `INC2190270` - *"Switch down / IDF down"*)
- **Site `3031`** with error `'Node Down'` (237 occurrences, Ticket `INC2182392` - *"Hard down"*)
- **Site `0001`** with error `'Node Down'` (5 occurrences, Ticket `INC2171831` - *"Internet dropping in warehouse"*)

---

## 7. Connecting from Python Code (Backend Team Integration)

Here is a ready-to-use Python snippet for the Backend team:

```python
import sqlite3

def get_site_error_ticket_history(site_code: str, error_type: str, db_path='noc_automation.db'):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Returns rows as dictionary-like objects
    cursor = conn.cursor()
    
    query = """
    WITH site_error_stats AS (
        SELECT 
            d.site_code,
            e.event_type_name AS error_type,
            COUNT(e.event_id) AS times_error_occurred_at_site
        FROM devices d
        JOIN event_logs e ON e.device_id = d.device_id
        WHERE d.site_code = ? AND e.event_type_name = ?
        GROUP BY d.site_code, e.event_type_name
    )
    SELECT 
        d.site_code,
        ses.error_type,
        ses.times_error_occurred_at_site,
        t.ticket_number,
        t.state,
        t.short_description,
        t.work_notes,
        GROUP_CONCAT(DISTINCT d.device_name) AS devices
    FROM devices d
    JOIN site_error_stats ses ON ses.site_code = d.site_code
    JOIN device_ticket_map m  ON m.device_id = d.device_id
    JOIN sn_tickets t         ON t.ticket_id = m.ticket_id
    WHERE d.site_code = ?
    GROUP BY t.ticket_id;
    """
    
    cursor.execute(query, (site_code, error_type, site_code))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

# Test run:
if __name__ == '__main__':
    data = get_site_error_ticket_history('8395', 'Node Down')
    for item in data:
        print(f"[{item['ticket_number']}] ({item['state']}): {item['short_description']}")
        print(f"  Error count at site: {item['times_error_occurred_at_site']}")
```

---

## 8. Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| `'python' is not recognized` | Python not added to Windows PATH | Re-run Python installer, choose "Modify", check "Add Python to PATH" |
| `ModuleNotFoundError: No module named 'pandas'` | pandas not installed | Run `pip install pandas` in terminal |
| `UnicodeDecodeError: 'utf-8' codec can't decode byte 0x97` | ServiceNow CSV has non-UTF-8 characters | `etl_pipeline.py` already handles this with `encoding='latin-1'` |
| `database is locked` | Another program (DB Browser) has a transaction open | In DB Browser, click "Write Changes" or close DB Browser |
