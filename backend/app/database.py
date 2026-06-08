from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .config import DATA_DIR, DB_PATH


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                workdir TEXT,
                command_preview TEXT,
                created_at TEXT NOT NULL
            )
            """
        )


def record_job_event(
    job_id: str,
    username: str,
    action: str,
    workdir: str | None = None,
    command: str | None = None,
) -> None:
    init_db()
    preview = None if command is None else command[:500]
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO job_events(job_id, username, action, workdir, command_preview, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, username, action, workdir, preview, now),
        )

