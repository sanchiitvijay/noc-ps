import sqlite3

from database.migrations import _migrate_ticket_solution_summaries


def test_legacy_summary_migration_preserves_rows_and_is_repeatable():
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE event_logs (event_id INTEGER PRIMARY KEY, event_type_id INTEGER);
        INSERT INTO event_logs VALUES (101, 7);
        INSERT INTO event_logs VALUES (102, 7);
        CREATE TABLE ticket_solution_summaries (
            id INTEGER PRIMARY KEY,
            event_type_id INTEGER NOT NULL UNIQUE,
            hypothesis TEXT NOT NULL,
            recommended_steps TEXT NOT NULL,
            confidence TEXT NOT NULL,
            generated_by TEXT NOT NULL,
            source_tickets TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        INSERT INTO ticket_solution_summaries VALUES
            (1, 7, 'Legacy hypothesis', '["Check the link"]', 'high',
             'gemini', '["INC123"]', '2026-01-01', '2026-01-02');
        """
    )

    _migrate_ticket_solution_summaries(conn)
    _migrate_ticket_solution_summaries(conn)

    assert conn.execute(
        "SELECT event_id, hypothesis, generated_by FROM ticket_solution_summaries"
    ).fetchall() == [(101, "Legacy hypothesis", "gemini")]
    assert conn.execute(
        "SELECT count(*) FROM ticket_solution_summaries_legacy"
    ).fetchone()[0] == 1