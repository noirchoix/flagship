from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from typing import Any

class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                repo_name TEXT NOT NULL,
                upload_path TEXT NOT NULL,
                extracted_path TEXT NOT NULL,
                detected_stack TEXT NOT NULL,
                file_count INTEGER NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                score INTEGER NOT NULL,
                readiness TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            ''')

    def create_session(self, *, session_id: str, repo_name: str, upload_path: str, extracted_path: str, detected_stack: list[str], file_count: int):
        with self._connect() as conn:
            conn.execute('INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)', (session_id, repo_name, upload_path, extracted_path, json.dumps(detected_stack), file_count, time.time()))

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
        if not row: return None
        d = dict(row); d['detected_stack'] = json.loads(d['detected_stack'] or '[]')
        return d

    def sessions(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT 50').fetchall()
        out=[]
        for row in rows:
            d=dict(row); d['detected_stack']=json.loads(d['detected_stack'] or '[]'); out.append(d)
        return out

    def save_audit(self, session_id: str, payload: dict[str, Any], score: int, readiness: str):
        with self._connect() as conn:
            conn.execute('INSERT INTO audits(session_id,payload,score,readiness,created_at) VALUES(?,?,?,?,?)', (session_id, json.dumps(payload), score, readiness, time.time()))

    def audit_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute('SELECT COUNT(*) FROM audits').fetchone()[0])

    def memory(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute('SELECT key,value,created_at FROM memory WHERE session_id=? ORDER BY created_at DESC', (session_id,)).fetchall()]

    def remember(self, session_id: str, key: str, value: str):
        with self._connect() as conn:
            conn.execute('INSERT INTO memory(session_id,key,value,created_at) VALUES(?,?,?,?)', (session_id,key,value,time.time()))
