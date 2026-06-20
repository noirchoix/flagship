from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from ai_suite.modules.workflow.core.config import settings


class Store:
    def __init__(self, db_path: Path = settings.database_path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self.conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    repo_name TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    detected_stack TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS files (
                    session_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    PRIMARY KEY (session_id, path)
                );
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS memory (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def count(self, table: str) -> int:
        if table not in {"sessions", "workflows", "runs"}:
            raise ValueError("unsupported table")
        with self.conn() as conn:
            return int(conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"])

    def insert_session(self, session_id: str, repo_name: str, root_path: str, files: list[dict[str, Any]], detected_stack: list[str]) -> None:
        with self.conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions(id, repo_name, root_path, file_count, detected_stack) VALUES(?,?,?,?,?)",
                (session_id, repo_name, root_path, len(files), json.dumps(detected_stack)),
            )
            conn.executemany(
                "INSERT OR REPLACE INTO files(session_id, path, kind, size) VALUES(?,?,?,?)",
                [(session_id, f["path"], f["kind"], f["size"]) for f in files],
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.conn() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                return None
            data = dict(row)
            data["detected_stack"] = json.loads(data.get("detected_stack") or "[]")
            return data

    def list_files(self, session_id: str) -> list[dict[str, Any]]:
        with self.conn() as conn:
            return [dict(row) for row in conn.execute("SELECT path, kind, size FROM files WHERE session_id=? ORDER BY path", (session_id,))]

    def insert_workflow(self, workflow_id: str, session_id: str | None, title: str, objective: str, payload: dict[str, Any]) -> None:
        with self.conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO workflows(id, session_id, title, objective, payload) VALUES(?,?,?,?,?)",
                (workflow_id, session_id, title, objective, json.dumps(payload)),
            )

    def insert_run(self, run_id: str, workflow_id: str, payload: dict[str, Any]) -> None:
        with self.conn() as conn:
            conn.execute("INSERT OR REPLACE INTO runs(id, workflow_id, payload) VALUES(?,?,?)", (run_id, workflow_id, json.dumps(payload)))
