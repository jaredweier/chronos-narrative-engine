import re

with open("database_pg.py", "r") as f:
    content = f.read()

# Replace psycopg2 imports
content = content.replace("import psycopg2\nfrom psycopg2 import pool\nfrom psycopg2.extras import DictCursor", "import sqlite3")

# Replace connection pool logic
pool_logic = """
_db_pool = None

def get_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = pool.SimpleConnectionPool(1, 20,
            dsn=DB_URL,
            cursor_factory=DictCursor
        )
    return _db_pool

@contextmanager
def get_db_connection():
    pool_instance = get_pool()
    conn = pool_instance.getconn()
    try:
        yield conn
    finally:
        pool_instance.putconn(conn)
"""

sqlite_logic = """
def get_db_connection():
    db_path = DB_URL.replace("sqlite:///", "") if DB_URL.startswith("sqlite:///") else "chronos.db"
    conn = sqlite3.connect(db_path, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    return conn

# Dummy wrapper to match the context manager usage
@contextmanager
def get_db_connection():
    db_path = DB_URL.replace("sqlite:///", "") if DB_URL.startswith("sqlite:///") else "chronos.db"
    conn = sqlite3.connect(db_path, timeout=DB_TIMEOUT)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
"""
content = content.replace(pool_logic, sqlite_logic)

# Replace all %s with ? for sql queries
content = re.sub(r'\%s', '?', content)

# Replace execute(query).fetchone()['c'] -> execute(query).fetchone()['c'] - row_factory handles it

with open("database.py", "w") as f:
    f.write(content)
print("database.py converted to sqlite")
