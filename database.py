import sqlite3
import uuid
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import settings


def get_conn():
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            size INTEGER NOT NULL,
            mime_type TEXT,
            uploaded_by INTEGER,
            created_at REAL NOT NULL,
            download_count INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def add_file(
    original_name: str,
    stored_name: str,
    size: int,
    mime_type: Optional[str],
    uploaded_by: int,
) -> str:
    file_id = uuid.uuid4().hex
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO files (id, original_name, stored_name, size, mime_type, uploaded_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (file_id, original_name, stored_name, size, mime_type, uploaded_by, time.time()),
    )
    conn.commit()
    conn.close()
    return file_id


def get_file(file_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM files WHERE id = ? AND is_deleted = 0", (file_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_files(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT * FROM files
        WHERE is_deleted = 0
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_files() -> int:
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM files WHERE is_deleted = 0"
    ).fetchone()[0]
    conn.close()
    return count


def total_size() -> int:
    conn = get_conn()
    size = conn.execute(
        "SELECT COALESCE(SUM(size), 0) FROM files WHERE is_deleted = 0"
    ).fetchone()[0]
    conn.close()
    return size or 0


def increment_download(file_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE files SET download_count = download_count + 1 WHERE id = ?",
        (file_id,),
    )
    conn.commit()
    conn.close()


def soft_delete(file_id: str) -> bool:
    conn = get_conn()
    cur = conn.execute(
        "UPDATE files SET is_deleted = 1 WHERE id = ? AND is_deleted = 0",
        (file_id,),
    )
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected > 0


def hard_delete(file_id: str) -> Optional[str]:
    """Returns stored_name if deleted, else None"""
    conn = get_conn()
    row = conn.execute(
        "SELECT stored_name FROM files WHERE id = ?", (file_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    stored_name = row["stored_name"]
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    return stored_name
