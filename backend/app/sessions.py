from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any


SESSION_TTL_SECONDS = 12 * 60 * 60


@dataclass
class ClusterCredentials:
    username: str
    password: str = field(repr=False)
    bastion_host: str
    bastion_port: int
    inner_host: str
    inner_port: int
    direct: bool = False
    key_path: Path | None = None
    use_key: bool = True
    created_at: float = 0
    last_used: float = 0
    connection: Any = field(default=None, repr=False, compare=False)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ClusterCredentials] = {}
        self._lock = RLock()

    def create(self, credentials: ClusterCredentials) -> str:
        now = time.time()
        credentials.created_at = now
        credentials.last_used = now
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = credentials
        return token

    def get(self, token: str | None) -> ClusterCredentials | None:
        if not token:
            return None
        now = time.time()
        with self._lock:
            credentials = self._sessions.get(token)
            if credentials is None:
                return None
            if now - credentials.last_used > SESSION_TTL_SECONDS:
                self._sessions.pop(token, None)
                return None
            credentials.last_used = now
            return credentials

    def delete(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            credentials = self._sessions.pop(token, None)
        connection = getattr(credentials, "connection", None) if credentials else None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                token
                for token, credentials in self._sessions.items()
                if now - credentials.last_used > SESSION_TTL_SECONDS
            ]
            for token in expired:
                credentials = self._sessions.pop(token, None)
                connection = getattr(credentials, "connection", None) if credentials else None
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass


session_store = SessionStore()
