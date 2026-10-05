"""SQLite 数据层：文件元数据 + 分享链接。"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "cundrop.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = _conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            r2_key TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL DEFAULT 0,
            mime TEXT NOT NULL DEFAULT 'application/octet-stream',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS shares (
            token TEXT PRIMARY KEY,
            file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            password_hash TEXT,
            expires_at INTEGER,
            created_at INTEGER NOT NULL,
            views INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_files_created ON files(created_at DESC);
        """
    )
    c.commit()
    c.close()


def add_file(filename, r2_key, size, mime):
    c = _conn()
    cur = c.execute(
        "INSERT INTO files (filename, r2_key, size, mime, status, created_at)"
        " VALUES (?,?,?,?, 'pending', ?)",
        (filename, r2_key, size, mime, int(time.time())),
    )
    fid = cur.lastrowid
    c.commit()
    c.close()
    return fid


def complete_file(fid):
    c = _conn()
    c.execute("UPDATE files SET status='ready' WHERE id=?", (fid,))
    c.commit()
    c.close()


def list_files():
    c = _conn()
    rows = c.execute(
        "SELECT * FROM files WHERE status='ready' ORDER BY created_at DESC"
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_file(fid):
    c = _conn()
    r = c.execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
    c.close()
    return dict(r) if r else None


def delete_file(fid):
    c = _conn()
    r = c.execute("SELECT r2_key FROM files WHERE id=?", (fid,)).fetchone()
    key = r["r2_key"] if r else None
    c.execute("DELETE FROM shares WHERE file_id=?", (fid,))
    c.execute("DELETE FROM files WHERE id=?", (fid,))
    c.commit()
    c.close()
    return key


def stats():
    c = _conn()
    r = c.execute(
        "SELECT COUNT(*) n, COALESCE(SUM(size),0) s FROM files WHERE status='ready'"
    ).fetchone()
    shares = c.execute("SELECT COUNT(*) n FROM shares").fetchone()["n"]
    c.close()
    return {"files": r["n"], "bytes": r["s"], "shares": shares}


def create_share(token, file_id, password_hash, expires_at):
    c = _conn()
    c.execute(
        "INSERT INTO shares (token, file_id, password_hash, expires_at, created_at)"
        " VALUES (?,?,?,?,?)",
        (token, file_id, password_hash, expires_at, int(time.time())),
    )
    c.commit()
    c.close()


def get_share(token):
    c = _conn()
    r = c.execute(
        "SELECT s.*, f.filename, f.size, f.mime, f.r2_key"
        " FROM shares s JOIN files f ON f.id=s.file_id WHERE s.token=?",
        (token,),
    ).fetchone()
    c.close()
    return dict(r) if r else None


def bump_views(token):
    c = _conn()
    c.execute("UPDATE shares SET views=views+1 WHERE token=?", (token,))
    c.commit()
    c.close()


def list_shares():
    c = _conn()
    rows = c.execute(
        "SELECT s.*, f.filename, f.size FROM shares s"
        " JOIN files f ON f.id=s.file_id ORDER BY s.created_at DESC"
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def delete_share(token):
    c = _conn()
    c.execute("DELETE FROM shares WHERE token=?", (token,))
    c.commit()
    c.close()
