import psycopg2
from database import get_db_connection
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
from config import DB_PATH, DB_TIMEOUT
from logger import get_logger


logger = get_logger(__name__)



def add_phrase(officer_name: str, label: str, phrase_text: str, category: str = "General") -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            'INSERT INTO phrase_book (officer_name, category, label, phrase_text, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id',
            (officer_name, category, label.strip(), phrase_text.strip(), datetime.now().isoformat())
        )
        return cursor.fetchone()[0]


def get_phrases(officer_name: str, category: Optional[str] = None) -> List[Dict]:
    with get_db_connection() as conn:
        if category:
            rows = conn.execute(
                'SELECT * FROM phrase_book WHERE officer_name = %s AND category = %s ORDER BY use_count DESC, label',
                (officer_name, category)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM phrase_book WHERE officer_name = %s ORDER BY category, use_count DESC, label',
                (officer_name,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_phrase_categories(officer_name: str) -> List[str]:
    with get_db_connection() as conn:
        rows = conn.execute(
            'SELECT DISTINCT category FROM phrase_book WHERE officer_name = %s ORDER BY category',
            (officer_name,)
        ).fetchall()
        return [r['category'] for r in rows]


def use_phrase(phrase_id: int):
    with get_db_connection() as conn:
        conn.execute(
            'UPDATE phrase_book SET use_count = use_count + 1 WHERE id = %s', (phrase_id,)
        )


def delete_phrase(phrase_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute('DELETE FROM phrase_book WHERE id = %s', (phrase_id,))
        return cursor.rowcount > 0


def search_phrases(officer_name: str, query: str) -> List[Dict]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM phrase_book WHERE officer_name = %s AND (label LIKE %s OR phrase_text LIKE %s) ORDER BY use_count DESC LIMIT 20",
            (officer_name, f'%{query}%', f'%{query}%')
        ).fetchall()
        return [dict(r) for r in rows]


def save_snapshot(incident_id: str, officer_name: str, text: str, label: str = "AI Draft") -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            'INSERT INTO report_snapshots (incident_id, officer_name, snapshot_text, snapshot_label, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING id',
            (incident_id, officer_name, text, label, datetime.now().isoformat())
        )
        return cursor.fetchone()[0]


def get_snapshots(incident_id: str) -> List[Dict]:
    with get_db_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM report_snapshots WHERE incident_id = %s ORDER BY created_at DESC',
            (incident_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def export_phrases_to_json(officer: str, filepath: str) -> int:
    import json
    phrases = get_phrases(officer)
    data = []
    for p in phrases:
        data.append({
            "label": p["label"],
            "phrase_text": p["phrase_text"],
            "category": p.get("category", "General"),
        })
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"officer": officer, "phrases": data, "count": len(data)}, f, indent=2)
    logger.info("Exported %d phrases to %s", len(data), filepath)
    return len(data)


def import_phrases_from_json(officer: str, filepath: str) -> int:
    import json
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)
    phrases = raw.get("phrases", raw) if isinstance(raw, dict) else raw
    count = 0
    for item in phrases:
        label = item.get("label", "")
        text = item.get("phrase_text", item.get("text", ""))
        category = item.get("category", "Imported")
        if label and text:
            add_phrase(officer, label, text, category)
            count += 1
    logger.info("Imported %d phrases from %s", count, filepath)
    return count
