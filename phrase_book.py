import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
from config import DB_PATH, DB_TIMEOUT


_db_initialized = False


def initialize_phrase_book():
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute('''
            CREATE TABLE IF NOT EXISTS phrase_book (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                officer_name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                label TEXT NOT NULL,
                phrase_text TEXT NOT NULL,
                use_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_pb_officer ON phrase_book(officer_name)
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_pb_category ON phrase_book(category)
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS report_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                officer_name TEXT NOT NULL,
                snapshot_text TEXT NOT NULL,
                snapshot_label TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_rs_incident ON report_snapshots(incident_id)
        ''')
        conn.commit()
    finally:
        conn.close()


@contextmanager
def _get_conn():
    global _db_initialized
    if not _db_initialized:
        _db_initialized = True
        initialize_phrase_book()
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


def add_phrase(officer_name: str, label: str, phrase_text: str, category: str = "General") -> int:
    with _get_conn() as conn:
        cursor = conn.execute(
            'INSERT INTO phrase_book (officer_name, category, label, phrase_text, created_at) VALUES (?, ?, ?, ?, ?)',
            (officer_name, category, label.strip(), phrase_text.strip(), datetime.now().isoformat())
        )
        return cursor.lastrowid


def get_phrases(officer_name: str, category: Optional[str] = None) -> List[Dict]:
    with _get_conn() as conn:
        if category:
            rows = conn.execute(
                'SELECT * FROM phrase_book WHERE officer_name = ? AND category = ? ORDER BY use_count DESC, label',
                (officer_name, category)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM phrase_book WHERE officer_name = ? ORDER BY category, use_count DESC, label',
                (officer_name,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_phrase_categories(officer_name: str) -> List[str]:
    with _get_conn() as conn:
        rows = conn.execute(
            'SELECT DISTINCT category FROM phrase_book WHERE officer_name = ? ORDER BY category',
            (officer_name,)
        ).fetchall()
        return [r['category'] for r in rows]


def use_phrase(phrase_id: int):
    with _get_conn() as conn:
        conn.execute(
            'UPDATE phrase_book SET use_count = use_count + 1 WHERE id = ?', (phrase_id,)
        )


def delete_phrase(phrase_id: int) -> bool:
    with _get_conn() as conn:
        cursor = conn.execute('DELETE FROM phrase_book WHERE id = ?', (phrase_id,))
        return cursor.rowcount > 0


def search_phrases(officer_name: str, query: str) -> List[Dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM phrase_book WHERE officer_name = ? AND (label LIKE ? OR phrase_text LIKE ?) ORDER BY use_count DESC LIMIT 20",
            (officer_name, f'%{query}%', f'%{query}%')
        ).fetchall()
        return [dict(r) for r in rows]


def save_snapshot(incident_id: str, officer_name: str, text: str, label: str = "AI Draft") -> int:
    with _get_conn() as conn:
        cursor = conn.execute(
            'INSERT INTO report_snapshots (incident_id, officer_name, snapshot_text, snapshot_label, created_at) VALUES (?, ?, ?, ?, ?)',
            (incident_id, officer_name, text, label, datetime.now().isoformat())
        )
        return cursor.lastrowid


def get_snapshots(incident_id: str) -> List[Dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            'SELECT * FROM report_snapshots WHERE incident_id = ? ORDER BY created_at DESC',
            (incident_id,)
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == '__main__':
    initialize_phrase_book()
    print("Phrase book database initialized")
    cats = get_phrase_categories("TestOfficer")
    print(f"Categories for TestOfficer: {cats}")
    add_phrase("TestOfficer", "Test Phrase", "This is a test phrase for demonstration.", "General")
    phrases = get_phrases("TestOfficer", limit=5)
    for p in phrases:
        print(f"  [{p['category']}] {p['label']}: {p['phrase_text'][:60]}...")


