import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
from config import DB_PATH, DB_TIMEOUT


_db_initialized = False


def initialize_database():
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS legal_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                officer_name TEXT NOT NULL,
                document_type TEXT NOT NULL,
                submission_timestamp TEXT NOT NULL,
                unedited_ai_draft TEXT,
                final_approved_report TEXT,
                was_modified_by_human INTEGER DEFAULT 0,
                verification_signature_flag INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_officer_name ON legal_audit_logs(officer_name)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_document_type ON legal_audit_logs(document_type)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_incident_id ON legal_audit_logs(incident_id)
        ''')
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db_connection():
    global _db_initialized
    if not _db_initialized:
        _db_initialized = True
        initialize_database()
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_submission(
    incident_id: str,
    officer_name: str,
    document_type: str,
    ai_draft: str,
    final_report: Optional[str] = None,
    was_modified: bool = False,
    verified: bool = False
) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO legal_audit_logs 
            (incident_id, officer_name, document_type, submission_timestamp, 
             unedited_ai_draft, final_approved_report, was_modified_by_human, verification_signature_flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            incident_id,
            officer_name,
            document_type,
            datetime.now().isoformat(),
            ai_draft,
            final_report,
            1 if was_modified else 0,
            1 if verified else 0
        ))
        return cursor.lastrowid


def get_recent_corrections(officer_name: str, report_type: str, limit: int = 3) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT final_approved_report, unedited_ai_draft, was_modified_by_human
            FROM legal_audit_logs
            WHERE officer_name = ? 
            AND document_type = ?
            AND final_approved_report IS NOT NULL
            AND was_modified_by_human = 1
            ORDER BY submission_timestamp DESC
            LIMIT ?
        ''', (officer_name, report_type, limit))
        return [dict(row) for row in cursor.fetchall()]


def get_officer_history(officer_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT incident_id, document_type, submission_timestamp, was_modified_by_human
            FROM legal_audit_logs
            WHERE officer_name = ?
            ORDER BY submission_timestamp DESC
            LIMIT ?
        ''', (officer_name, limit))
        return [dict(row) for row in cursor.fetchall()]


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM legal_audit_logs
            WHERE incident_id = ?
            ORDER BY submission_timestamp DESC
            LIMIT 1
        ''', (incident_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_final_report(record_id: int, final_report: str, was_modified: bool = True):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE legal_audit_logs
            SET final_approved_report = ?, was_modified_by_human = ?
            WHERE id = ?
        ''', (final_report, 1 if was_modified else 0, record_id))


def get_statistics() -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM legal_audit_logs')
        total = cursor.fetchone()['total']
        
        cursor.execute('SELECT COUNT(*) as modified FROM legal_audit_logs WHERE was_modified_by_human = 1')
        modified = cursor.fetchone()['modified']
        
        cursor.execute('SELECT COUNT(*) as verified FROM legal_audit_logs WHERE verification_signature_flag = 1')
        verified = cursor.fetchone()['verified']
        
        cursor.execute('''
            SELECT document_type, COUNT(*) as count 
            FROM legal_audit_logs 
            GROUP BY document_type 
            ORDER BY count DESC
        ''')
        by_type = {row['document_type']: row['count'] for row in cursor.fetchall()}
        
        return {
            'total_submissions': total,
            'human_modified': modified,
            'verified': verified,
            'by_document_type': by_type
        }



if __name__ == '__main__':
    print("Database initialized at:", DB_PATH)
    stats = get_statistics()
    print("Current statistics:", stats)
