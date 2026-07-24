import hashlib
import hmac
import re
import secrets
import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor
import urllib.parse
import os
import time
from datetime import datetime, timedelta
from typing import Iterator, List, Dict, Optional, Any
from contextlib import contextmanager
from config import DB_URL, DB_TIMEOUT, DATA_RETENTION_DAYS
from logger import get_logger

logger = get_logger("database")

_db_initialized = False
_AUDIT_HMAC_KEY: bytes = os.environ.get("CHRONOS_AUDIT_HMAC_KEY", "").encode()
if not _AUDIT_HMAC_KEY:
    _KEY_FILE = os.path.join(os.path.dirname(DB_URL), ".chronos_hmac_key")
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as _kf:
            _AUDIT_HMAC_KEY = _kf.read().strip()
    else:
        _AUDIT_HMAC_KEY = hashlib.sha256(secrets.token_bytes(64)).digest()
        try:
            with open(_KEY_FILE, "wb") as _kf:
                _kf.write(_AUDIT_HMAC_KEY)
        except OSError:
            pass


_MIGRATIONS: List[Dict[str, Any]] = []


def _migration(version: int, description: str):
    def decorator(f):
        _MIGRATIONS.append({"version": version, "description": description, "func": f})
        return f
    return decorator


def _run_pending_migrations(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)
    applied = {row["version"] for row in cursor.execute(
        "SELECT version FROM schema_migrations ORDER BY version"
    ).fetchall()}
    for m in sorted(_MIGRATIONS, key=lambda x: x["version"]):
        if m["version"] not in applied:
            try:
                m["func"](cursor)
                cursor.execute(
                    "INSERT INTO schema_migrations (version, description, applied_at) VALUES (%s, %s, %s)",
                    (m["version"], m["description"], datetime.now().isoformat())
                )
            except psycopg2.OperationalError as e:
                if "duplicate column" not in str(e).lower():
                    raise


@_migration(1, "Add review/reviewer columns to legal_audit_logs")
def _migrate_001(cursor):
    for col, dtype in [
        ("previous_hash", "TEXT NOT NULL DEFAULT ''"),
        ("review_status", "TEXT NOT NULL DEFAULT 'submitted'"),
        ("reviewer_notes", "TEXT DEFAULT ''"),
        ("reviewed_by", "TEXT DEFAULT ''"),
        ("reviewed_at", "TEXT DEFAULT ''"),
        ("related_cases", "TEXT DEFAULT ''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE legal_audit_logs ADD COLUMN {col} {dtype}")
        except psycopg2.OperationalError:
            pass


@_migration(2, "Add ip_address to login_attempts")
def _migrate_002(cursor):
    try:
        cursor.execute("ALTER TABLE login_attempts ADD COLUMN ip_address TEXT DEFAULT ''")
    except psycopg2.OperationalError:
        pass


@_migration(3, "Create spell_custom_dict table")
def _migrate_003(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spell_custom_dict (
            id SERIAL PRIMARY KEY,
            misspelling TEXT NOT NULL UNIQUE,
            correction TEXT NOT NULL,
            added_by TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)


@_migration(4, "Add theme_pref to officer_users")
def _migrate_004(cursor):
    try:
        cursor.execute("ALTER TABLE officer_users ADD COLUMN theme_pref TEXT DEFAULT 'dark'")
    except psycopg2.OperationalError:
        pass


@_migration(5, "Create report_snapshots table with version tracking")
def _migrate_005(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_snapshots (
            id SERIAL PRIMARY KEY,
            incident_id TEXT NOT NULL,
            snapshot_text TEXT NOT NULL,
            label TEXT DEFAULT '',
            officer_name TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            previous_snapshot_id INTEGER DEFAULT NULL,
            FOREIGN KEY (previous_snapshot_id) REFERENCES report_snapshots(id)
        )
    """)
    try:
        cursor.execute("ALTER TABLE report_snapshots ADD COLUMN previous_snapshot_id INTEGER DEFAULT NULL")
    except psycopg2.OperationalError:
        pass



_db_pool = None

def get_pool():
    global _db_pool
    if _db_pool is None:
        urllib.parse.uses_netloc.append("postgres")
        url = urllib.parse.urlparse(DB_URL)
        _db_pool = pool.SimpleConnectionPool(1, 20,
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
    return _db_pool

def initialize_database() -> None:
    conn = get_pool().getconn()
    
    try:
        pass
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS legal_audit_logs (
                id SERIAL PRIMARY KEY,
                incident_id TEXT NOT NULL,
                officer_name TEXT NOT NULL,
                officer_id TEXT NOT NULL DEFAULT '',
                document_type TEXT NOT NULL,
                submission_timestamp TEXT NOT NULL,
                unedited_ai_draft TEXT,
                final_approved_report TEXT,
                was_modified_by_human INTEGER DEFAULT 0,
                verification_signature_flag INTEGER DEFAULT 0,
                previous_hash TEXT NOT NULL DEFAULT '',
                row_hash TEXT NOT NULL DEFAULT ''
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evidence_chain (
                id SERIAL PRIMARY KEY,
                incident_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                description TEXT NOT NULL,
                evidence_type TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                notes TEXT DEFAULT ''
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_evidence_incident ON evidence_chain(incident_id)
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id SERIAL PRIMARY KEY,
                badge_id TEXT NOT NULL,
                attempt_time REAL NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                ip_address TEXT DEFAULT ''
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_login_badge ON login_attempts(badge_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_login_time ON login_attempts(attempt_time)
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS login_audit_log (
                id SERIAL PRIMARY KEY,
                badge_id TEXT NOT NULL,
                officer_name TEXT,
                attempt_time TEXT NOT NULL,
                ip_address TEXT DEFAULT '',
                success INTEGER NOT NULL DEFAULT 0,
                failure_reason TEXT DEFAULT ''
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_login_audit_badge ON login_audit_log(badge_id)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evidence_files (
                id SERIAL PRIMARY KEY,
                incident_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                mime_type TEXT DEFAULT '',
                uploaded_by TEXT DEFAULT '',
                uploaded_at TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'other'
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_evidence_files_incident ON evidence_files(incident_id)
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS officer_users (
                badge_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                role TEXT DEFAULT 'officer',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT DEFAULT ''
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id SERIAL PRIMARY KEY,
                badge_id TEXT NOT NULL,
                login_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                ip_address TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sessions_badge ON user_sessions(badge_id)
        ''')

        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS report_search_index USING fts5(
                incident_id, officer_name, document_type, narrative_text,
                content='legal_audit_logs',
                content_rowid='id'
            )
        ''')
        _run_pending_migrations(cursor)
        conn.commit()
    finally:
        if conn:
            get_pool().putconn(conn)


@contextmanager
def get_db_connection():
    global _db_initialized
    if not _db_initialized:
        _db_initialized = True
        initialize_database()
    conn = get_pool().getconn()
    
    try:
        pass
        pass
        yield conn
        conn.commit()
    except psycopg2.OperationalError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        if conn:
            get_pool().putconn(conn)


def close_all_connections() -> None:
    pass


def _compute_row_hash(row_id: int, prev_hash: str, fields: Dict[str, Any]) -> str:
    parts = [str(row_id), prev_hash]
    for k in sorted(fields.keys()):
        parts.append(str(fields[k]))
    payload = "|".join(parts)
    return hmac.new(_AUDIT_HMAC_KEY, payload.encode(), hashlib.sha256).hexdigest()


def _get_last_audit_hash() -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute("SELECT row_hash FROM legal_audit_logs ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row["row_hash"]
    except Exception:
        pass
    return ""


def log_submission(
    incident_id: str,
    officer_name: str,
    officer_id: str = '',
    document_type: str = '',
    ai_draft: str = '',
    final_report: Optional[str] = None,
    was_modified: bool = False,
    verified: bool = False
) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        prev_hash = _get_last_audit_hash()
        fields = {
            "incident_id": incident_id,
            "officer_name": officer_name,
            "officer_id": officer_id,
            "document_type": document_type,
            "submission_timestamp": datetime.now().isoformat(),
            "unedited_ai_draft": ai_draft,
            "final_approved_report": final_report or "",
            "was_modified_by_human": 1 if was_modified else 0,
            "verification_signature_flag": 1 if verified else 0,
            "previous_hash": prev_hash,
        }
        cursor.execute('''
            INSERT INTO legal_audit_logs 
            (incident_id, officer_name, officer_id, document_type, submission_timestamp, 
             unedited_ai_draft, final_approved_report, was_modified_by_human,
             verification_signature_flag, previous_hash, row_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''', (
            fields["incident_id"],
            fields["officer_name"],
            fields["officer_id"],
            fields["document_type"],
            fields["submission_timestamp"],
            fields["unedited_ai_draft"],
            fields["final_approved_report"],
            fields["was_modified_by_human"],
            fields["verification_signature_flag"],
            fields["previous_hash"],
            "",
        ))
        row_id = cursor.fetchone()[0]
        row_hash = _compute_row_hash(row_id, prev_hash, fields)
        cursor.execute("UPDATE legal_audit_logs SET row_hash = %s WHERE id = %s", (row_hash, row_id))
        return row_id


def get_recent_corrections(officer_name: str, report_type: str, limit: int = 3) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('''
            SELECT final_approved_report, unedited_ai_draft, was_modified_by_human
            FROM legal_audit_logs
            WHERE officer_name = %s 
            AND document_type = %s
            AND final_approved_report IS NOT NULL
            AND was_modified_by_human = 1
            ORDER BY submission_timestamp DESC
            LIMIT %s
        ''', (officer_name, report_type, limit))
        return [dict(row) for row in cursor.fetchall()]


def get_officer_history(officer_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('''
            SELECT incident_id, document_type, submission_timestamp, was_modified_by_human
            FROM legal_audit_logs
            WHERE officer_name = %s
            ORDER BY submission_timestamp DESC
            LIMIT %s
        ''', (officer_name, limit))
        return [dict(row) for row in cursor.fetchall()]


def get_incident(incident_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('''
            SELECT * FROM legal_audit_logs
            WHERE incident_id = %s
            ORDER BY submission_timestamp DESC
            LIMIT 1
        ''', (incident_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_statistics() -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        
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



def add_evidence_event(
    incident_id: str,
    evidence_id: str,
    description: str,
    evidence_type: str,
    action: str,
    actor: str,
    notes: str = "",
) -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('''
            INSERT INTO evidence_chain
            (incident_id, evidence_id, description, evidence_type, action, actor, timestamp, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id''', (
            incident_id,
            evidence_id,
            description,
            evidence_type,
            action,
            actor,
            datetime.now().isoformat(),
            notes,
        ))
        return cursor.fetchone()[0]


def get_evidence_chain(incident_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('''
            SELECT * FROM evidence_chain
            WHERE incident_id = %s
            ORDER BY timestamp ASC
        ''', (incident_id,))
        return [dict(row) for row in cursor.fetchall()]


def check_login_rate_limit(badge_id: str, max_attempts: int = 5, lockout_minutes: int = 15, ip_address: str = "") -> bool:
    now = time.time()
    cutoff = now - lockout_minutes * 60
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute(
            'SELECT COUNT(*) as cnt FROM login_attempts WHERE badge_id = %s AND attempt_time > %s AND success = 0',
            (badge_id, cutoff)
        )
        badge_cnt = cursor.fetchone()['cnt']
        if badge_cnt >= max_attempts:
            return False
        if ip_address:
            cursor.execute(
                'SELECT COUNT(*) as cnt FROM login_attempts WHERE ip_address = %s AND attempt_time > %s AND success = 0',
                (ip_address, cutoff)
            )
            ip_cnt = cursor.fetchone()['cnt']
            return ip_cnt < max_attempts
        return True


def record_login_attempt(badge_id: str, success: bool, ip_address: str = "") -> None:
    with get_db_connection() as conn:
        conn.cursor(cursor_factory=DictCursor).execute(
            'INSERT INTO login_attempts (badge_id, attempt_time, success, ip_address) VALUES (%s, %s, %s, %s)',
            (badge_id, time.time(), 1 if success else 0, ip_address)
        )


def log_login_audit(badge_id: str, officer_name: str, success: bool, failure_reason: str = '', ip_address: str = '') -> None:
    with get_db_connection() as conn:
        conn.cursor(cursor_factory=DictCursor).execute(
            'INSERT INTO login_audit_log (badge_id, officer_name, attempt_time, success, failure_reason, ip_address) VALUES (%s, %s, %s, %s, %s, %s)',
            (badge_id, officer_name, datetime.now().isoformat(), 1 if success else 0, failure_reason, ip_address)
        )


def update_review_status(incident_id: str, status: str, reviewer: str = '', notes: str = '') -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute(
            "UPDATE legal_audit_logs SET review_status = %s, reviewed_by = %s, reviewer_notes = %s, reviewed_at = %s WHERE incident_id = %s",
            (status, reviewer, notes, datetime.now().isoformat(), incident_id)
        )
        return cursor.rowcount > 0


def get_pending_reviews(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            """SELECT incident_id, officer_name, officer_id, document_type, submission_timestamp,
                      review_status, reviewed_by, reviewer_notes, final_approved_report, unedited_ai_draft
               FROM legal_audit_logs
               WHERE review_status IN ('submitted', 'reviewed')
               ORDER BY submission_timestamp DESC
               LIMIT %s""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_review_counts() -> Dict[str, int]:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        counts = {}
        for status in ('submitted', 'reviewed', 'approved', 'rejected'):
            cursor.execute("SELECT COUNT(*) as cnt FROM legal_audit_logs WHERE review_status = %s", (status,))
            counts[status] = cursor.fetchone()['cnt']
        cursor.execute("SELECT COUNT(*) as cnt FROM legal_audit_logs WHERE review_status IN ('submitted','reviewed')")
        counts['pending'] = cursor.fetchone()['cnt']
        return counts


def backup_database() -> bytes:
    return b""

def restore_database(data: bytes) -> bool:
    return False

def link_cases(primary_id: str, related_id: str, relation: str = 'related') -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute(
            "UPDATE legal_audit_logs SET related_cases = COALESCE(related_cases || ', ', '') || %s WHERE incident_id = %s",
            (f"{related_id}:{relation}", primary_id)
        )
        cursor.execute(
            "UPDATE legal_audit_logs SET related_cases = COALESCE(related_cases || ', ', '') || %s WHERE incident_id = %s",
            (f"{primary_id}:{relation}", related_id)
        )
        return True


def get_related_cases(incident_id: str) -> List[Dict[str, str]]:
    with get_db_connection() as conn:
        row = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT related_cases FROM legal_audit_logs WHERE incident_id = %s", (incident_id,)
        ).fetchone()
        if not row or not row['related_cases']:
            return []
        related = []
        for entry in row['related_cases'].split(', '):
            parts = entry.split(':', 1)
            if len(parts) == 2:
                related.append({"incident_id": parts[0], "relation": parts[1]})
        return related


# --- Full-Text Search ---

_FTS5_SPECIAL_RE = re.compile(r'[\^$(){}[\]"*%s:\\~#@]')


def _tokenize_or_query(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        return stripped
    if any(op in stripped for op in (" OR ", " AND ", " NOT ", '"')):
        return stripped
    tokens = stripped.split()
    escaped = [_FTS5_SPECIAL_RE.sub("", t) for t in tokens if t]
    if not escaped:
        return stripped
    return " OR ".join(escaped)


def rebuild_search_index() -> None:
    with get_db_connection() as conn:
        try:
            conn.cursor(cursor_factory=DictCursor).execute("INSERT INTO report_search_index(report_search_index) VALUES('delete-all')")
        except psycopg2.OperationalError:
            conn.cursor(cursor_factory=DictCursor).execute("DELETE FROM report_search_index")
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT id, incident_id, officer_name, document_type, COALESCE(final_approved_report, unedited_ai_draft, '') as text FROM legal_audit_logs"
        ).fetchall()
        for r in rows:
            try:
                conn.cursor(cursor_factory=DictCursor).execute(
                    "INSERT INTO report_search_index (rowid, incident_id, officer_name, document_type, narrative_text) VALUES (%s, %s, %s, %s, %s)",
                    (r['id'], r['incident_id'], r['officer_name'], r['document_type'], r['text'])
                )
            except psycopg2.OperationalError:
                pass


def search_reports(query: str, limit: int = 30, raw_query: bool = False) -> List[Dict[str, Any]]:
    if not query:
        return []
    fts5_query = query if raw_query else _tokenize_or_query(query)
    if not fts5_query:
        return []
    with get_db_connection() as conn:
        try:
            rows = conn.cursor(cursor_factory=DictCursor).execute(
                """SELECT l.* FROM report_search_index f
                   JOIN legal_audit_logs l ON l.id = f.rowid
                   WHERE report_search_index @@ to_tsquery(%s)
                   ORDER BY rank
                   LIMIT %s""",
                (fts5_query, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except psycopg2.OperationalError:
            rebuild_search_index()
            return search_reports(query, limit)


def search_officer_reports(officer_name: str, query: str, limit: int = 20, raw_query: bool = False) -> List[Dict[str, Any]]:
    if not query:
        return []
    fts5_query = query if raw_query else _tokenize_or_query(query)
    if not fts5_query:
        return []
    with get_db_connection() as conn:
        try:
            rows = conn.cursor(cursor_factory=DictCursor).execute(
                """SELECT l.* FROM report_search_index f
                   JOIN legal_audit_logs l ON l.id = f.rowid
                   WHERE report_search_index @@ to_tsquery(%s) AND l.officer_name = %s
                   ORDER BY rank
                   LIMIT %s""",
                (fts5_query, officer_name, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        except psycopg2.OperationalError:
            rebuild_search_index()
            return search_officer_reports(officer_name, query, limit)


# --- Evidence Locker ---

def save_evidence_file(incident_id: str, file_name: str, file_path: str, file_size: int,
                       mime_type: str, uploaded_by: str, description: str = "", category: str = "other") -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor).execute(
            """INSERT INTO evidence_files (incident_id, file_name, file_path, file_size, mime_type, uploaded_by, uploaded_at, description, category)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (incident_id, file_name, file_path, file_size, mime_type, uploaded_by,
             datetime.now().isoformat(), description, category)
        )
        return cursor.fetchone()[0]


def get_evidence_files(incident_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT * FROM evidence_files WHERE incident_id = %s ORDER BY uploaded_at DESC",
            (incident_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_evidence_file(file_id: int) -> bool:
    with get_db_connection() as conn:
        row = conn.cursor(cursor_factory=DictCursor).execute("SELECT file_path FROM evidence_files WHERE id = %s", (file_id,)).fetchone()
        if row:
            path = row['file_path']
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        conn.cursor(cursor_factory=DictCursor).execute("DELETE FROM evidence_files WHERE id = %s", (file_id,))
        return True


def get_all_evidence_file_categories() -> List[str]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute("SELECT DISTINCT category FROM evidence_files ORDER BY category").fetchall()
        return [r['category'] for r in rows]


# --- User Management ---

def get_all_users() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT * FROM officer_users ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_user(badge_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT * FROM officer_users WHERE badge_id = %s", (badge_id,)
        ).fetchone()
        return dict(row) if row else None


def upsert_user(badge_id: str, name: str, role: str, email: str = "", phone: str = "",
                is_active: bool = True) -> bool:
    with get_db_connection() as conn:
        existing = conn.cursor(cursor_factory=DictCursor).execute("SELECT badge_id FROM officer_users WHERE badge_id = %s", (badge_id,)).fetchone()
        if existing:
            conn.cursor(cursor_factory=DictCursor).execute(
                "UPDATE officer_users SET name=%s, role=%s, email=%s, phone=%s, is_active=%s WHERE badge_id=%s",
                (name, role, email, phone, 1 if is_active else 0, badge_id)
            )
        else:
            conn.cursor(cursor_factory=DictCursor).execute(
                "INSERT INTO officer_users (badge_id, name, role, email, phone, is_active, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (badge_id, name, role, email, phone, 1 if is_active else 0, datetime.now().isoformat())
            )
        return True


def deactivate_user(badge_id: str) -> bool:
    with get_db_connection() as conn:
        conn.cursor(cursor_factory=DictCursor).execute("UPDATE officer_users SET is_active = 0 WHERE badge_id = %s", (badge_id,))
        return True


def activate_user(badge_id: str) -> bool:
    with get_db_connection() as conn:
        conn.cursor(cursor_factory=DictCursor).execute("UPDATE officer_users SET is_active = 1 WHERE badge_id = %s", (badge_id,))
        return True


def record_user_login(badge_id: str, ip_address: str = "") -> None:
    with get_db_connection() as conn:
        now = datetime.now().isoformat()
        conn.cursor(cursor_factory=DictCursor).execute(
            "UPDATE officer_users SET last_login = %s WHERE badge_id = %s", (now, badge_id)
        )
        conn.cursor(cursor_factory=DictCursor).execute(
            "INSERT INTO user_sessions (badge_id, login_at, last_activity, ip_address) VALUES (%s, %s, %s, %s)",
            (badge_id, now, now, ip_address)
        )


def get_user_sessions(badge_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT * FROM user_sessions WHERE badge_id = %s ORDER BY login_at DESC LIMIT %s",
            (badge_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]


# --- Data Retention ---

def purge_old_records(days: int = DATA_RETENTION_DAYS) -> int:
    if days <= 0:
        return 0
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    to_delete: list = []
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT id, incident_id FROM legal_audit_logs WHERE submission_timestamp < %s",
            (cutoff,)
        )
        to_delete = [dict(r) for r in cursor.fetchall()]
        files_removed = 0
        for entry in to_delete:
            file_rows = conn.cursor(cursor_factory=DictCursor).execute(
                "SELECT file_path FROM evidence_files WHERE incident_id = %s", (entry['incident_id'],)
            ).fetchall()
            for fr in file_rows:
                fp = fr['file_path']
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                        files_removed += 1
                    except OSError:
                        pass
            conn.cursor(cursor_factory=DictCursor).execute(
                "DELETE FROM evidence_files WHERE incident_id = %s", (entry['incident_id'],)
            )
            conn.cursor(cursor_factory=DictCursor).execute(
                "DELETE FROM legal_audit_logs WHERE id = %s", (entry['id'],)
            )
    if to_delete:
        logger.info("Purged %d old records and %d evidence files from disk", len(to_delete), files_removed)
        rebuild_search_index()
    return len(to_delete)


# --- Spell Check Custom Dictionary ---


def add_custom_correction(misspelling: str, correction: str, added_by: str = '') -> bool:
    with get_db_connection() as conn:
        try:
            conn.cursor(cursor_factory=DictCursor).execute(
                "INSERT OR IGNORE INTO spell_custom_dict (misspelling, correction, added_by, created_at) VALUES (%s, %s, %s, %s)",
                (misspelling, correction, added_by, datetime.now().isoformat())
            )
            return conn.total_changes > 0
        except psycopg2.IntegrityError:
            return False


def remove_custom_correction(misspelling: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor).execute(
            "UPDATE spell_custom_dict SET is_active = 0 WHERE misspelling = %s",
            (misspelling,)
        )
        return cursor.rowcount > 0


def get_custom_corrections() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT * FROM spell_custom_dict WHERE is_active = 1 ORDER BY misspelling"
        ).fetchall()
        return [dict(r) for r in rows]


def get_custom_dict() -> Dict[str, str]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT misspelling, correction FROM spell_custom_dict WHERE is_active = 1"
        ).fetchall()
        return {r['misspelling']: r['correction'] for r in rows}


# --- Theme Preference ---


def set_theme_preference(badge_id: str, theme: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor).execute(
            "UPDATE officer_users SET theme_pref = %s WHERE badge_id = %s",
            (theme, badge_id)
        )
        return cursor.rowcount > 0


def get_theme_preference(badge_id: str) -> str:
    with get_db_connection() as conn:
        row = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT theme_pref FROM officer_users WHERE badge_id = %s",
            (badge_id,)
        ).fetchone()
        if row:
            return row['theme_pref']
        return 'dark'


def delete_reports(ids: List[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("%s" for _ in ids)
    count = len(ids)
    with get_db_connection() as conn:
        conn.cursor(cursor_factory=DictCursor).execute(
            f"DELETE FROM legal_audit_logs WHERE id IN ({placeholders})", ids
        )
    rebuild_search_index()
    return count


# --- Dashboard Analytics Extensions ---

def get_dashboard_analytics(days: int = 30) -> Dict[str, Any]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with get_db_connection() as conn:
        total = conn.cursor(cursor_factory=DictCursor).execute("SELECT COUNT(*) as c FROM legal_audit_logs").fetchone()['c']
        recent = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT COUNT(*) as c FROM legal_audit_logs WHERE submission_timestamp >= %s",
            (cutoff,)
        ).fetchone()['c']
        officers = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT COUNT(DISTINCT officer_name) as c FROM legal_audit_logs WHERE submission_timestamp >= %s",
            (cutoff,)
        ).fetchone()['c']
        active_users = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT COUNT(*) as c FROM officer_users WHERE is_active = 1"
        ).fetchone()['c']
        evidence_count = conn.cursor(cursor_factory=DictCursor).execute("SELECT COUNT(*) as c FROM evidence_files").fetchone()['c']
        return {
            "total_reports": total,
            "recent_reports": recent,
            "active_officers": officers,
            "registered_users": active_users,
            "evidence_items": evidence_count,
        }


# --- Login Audit Viewer ---

def get_login_audit_logs(limit: int = 100, badge_id: str = "") -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        if badge_id:
            rows = conn.cursor(cursor_factory=DictCursor).execute(
                "SELECT * FROM login_audit_log WHERE badge_id = %s ORDER BY attempt_time DESC LIMIT %s",
                (badge_id, limit)
            ).fetchall()
        else:
            rows = conn.cursor(cursor_factory=DictCursor).execute(
                "SELECT * FROM login_audit_log ORDER BY attempt_time DESC LIMIT %s", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# --- Audit Chain Verification ---

def verify_audit_chain() -> List[Dict[str, Any]]:
    results = []
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT id, incident_id, officer_name, submission_timestamp, "
            "previous_hash, row_hash FROM legal_audit_logs ORDER BY id ASC"
        ).fetchall()
    expected_prev = ""
    for r in rows:
        row_id = r["id"]
        if r["previous_hash"] != expected_prev:
            results.append({
                "id": row_id,
                "incident_id": r["incident_id"],
                "status": "BROKEN_CHAIN",
                "expected_prev": expected_prev,
                "actual_prev": r["previous_hash"],
            })
        expected_prev = r["row_hash"]
    if not results:
        results.append({"status": "INTACT", "total_rows": len(rows)})
    return results


# --- Report Snapshots ---

def save_snapshot_db(incident_id: str, text: str, label: str = "", officer: str = "") -> int:
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute(
            "SELECT id FROM report_snapshots WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1",
            (incident_id,)
        )
        prev_row = cursor.fetchone()
        prev_id = prev_row["id"] if prev_row else None
        cursor.execute(
            "INSERT INTO report_snapshots (incident_id, snapshot_text, label, officer_name, created_at, previous_snapshot_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (incident_id, text, label, officer, datetime.now().isoformat(), prev_id)
        )
        return cursor.fetchone()[0]


def get_snapshots(incident_id: str) -> List[Dict]:
    with get_db_connection() as conn:
        rows = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT * FROM report_snapshots WHERE incident_id = %s ORDER BY created_at ASC",
            (incident_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_snapshot_by_id(snapshot_id: int) -> Optional[Dict]:
    with get_db_connection() as conn:
        row = conn.cursor(cursor_factory=DictCursor).execute(
            "SELECT * FROM report_snapshots WHERE id = %s", (snapshot_id,)
        ).fetchone()
        return dict(row) if row else None


if __name__ == '__main__':
    print("Database initialized at:", DB_URL)
    stats = get_statistics()
    print("Current statistics:", stats)
