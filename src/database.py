"""
SQLite audit trail for the Finance Email Agent.

Every generated email, skipped invoice, and escalation flag is logged here
with full metadata for compliance and audit purposes.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional


class AuditDB:
    """
    Manages a SQLite database for audit logging of all agent actions.

    Table schema:
        id, timestamp, invoice_no, client_name, amount, days_overdue,
        stage, tone, status, subject, body, send_method, contact_email_masked
    """

    def __init__(self, db_path: str = "logs/audit.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        """Create the audit_log table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT    NOT NULL,
                    invoice_no      TEXT    NOT NULL,
                    client_name     TEXT,
                    amount          REAL,
                    days_overdue    INTEGER,
                    stage           INTEGER DEFAULT 0,
                    tone            TEXT    DEFAULT '',
                    status          TEXT    NOT NULL,
                    subject         TEXT    DEFAULT '',
                    body            TEXT    DEFAULT '',
                    send_method     TEXT    DEFAULT 'dry_run',
                    contact_email_masked TEXT DEFAULT ''
                )
            ''')
            conn.commit()

    def log_entry(self, entry: dict):
        """Insert a single audit log entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO audit_log (
                    timestamp, invoice_no, client_name, amount, days_overdue,
                    stage, tone, status, subject, body, send_method, contact_email_masked
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.get('timestamp', datetime.now().isoformat()),
                entry.get('invoice_no', ''),
                entry.get('client_name', ''),
                entry.get('amount', 0.0),
                entry.get('days_overdue', 0),
                entry.get('stage', 0),
                entry.get('tone', ''),
                entry.get('status', ''),
                entry.get('subject', ''),
                entry.get('body', ''),
                entry.get('send_method', 'dry_run'),
                entry.get('contact_email_masked', ''),
            ))
            conn.commit()

    def get_all_logs(self) -> List[Dict]:
        """Retrieve all audit log entries, newest first."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM audit_log ORDER BY timestamp DESC')
            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict:
        """Return summary statistics for the dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            total = conn.execute('SELECT COUNT(*) as c FROM audit_log').fetchone()['c']
            sent = conn.execute("SELECT COUNT(*) as c FROM audit_log WHERE status = 'generated'").fetchone()['c']
            escalated = conn.execute("SELECT COUNT(*) as c FROM audit_log WHERE status = 'escalated'").fetchone()['c']
            skipped = conn.execute("SELECT COUNT(*) as c FROM audit_log WHERE status = 'skipped'").fetchone()['c']
            errors = conn.execute("SELECT COUNT(*) as c FROM audit_log WHERE status = 'error'").fetchone()['c']

            # Stage distribution
            stage_dist = {}
            rows = conn.execute(
                "SELECT stage, COUNT(*) as c FROM audit_log WHERE status = 'generated' GROUP BY stage"
            ).fetchall()
            for row in rows:
                stage_dist[f"Stage {row['stage']}"] = row['c']

            return {
                "total_processed": total,
                "emails_sent": sent,
                "escalated": escalated,
                "skipped": skipped,
                "errors": errors,
                "stage_distribution": stage_dist,
            }

    def clear_logs(self):
        """Clear all audit log entries (useful for testing)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM audit_log')
            conn.commit()
