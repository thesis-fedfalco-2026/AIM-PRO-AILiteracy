"""Server-side login and session state (D8): the browser holds only a random session id.

The store is process-local and lost on restart; a shared store is needed
before several API processes serve the same users.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass(frozen=True)
class PendingLogin:
    state: str
    nonce: str
    code_verifier: str = field(repr=False)
    return_to: str
    expires_at: float


@dataclass(frozen=True)
class Session:
    id: str = field(repr=False)
    issuer: str
    subject: str
    csrf_token: str = field(repr=False)
    id_token: str = field(repr=False)
    access_token: str = field(repr=False)
    refresh_token: str | None = field(repr=False)
    expires_at: float


class MemorySessionStore:
    def __init__(self):
        self._lock = Lock()
        self._logins: dict[str, PendingLogin] = {}
        self._sessions: dict[str, Session] = {}

    def _purge(self, now: float) -> None:
        for table in (self._logins, self._sessions):
            for key in [key for key, value in table.items() if value.expires_at <= now]:
                del table[key]

    def begin_login(self, login: PendingLogin, now: float) -> None:
        with self._lock:
            self._purge(now)
            self._logins[login.state] = login

    def finish_login(self, state: str, now: float) -> PendingLogin | None:
        """The pending login for ``state``, removed so that it is used at most once."""
        with self._lock:
            login = self._logins.pop(state, None)
        return login if login is not None and now < login.expires_at else None

    def create(self, session: Session, now: float) -> None:
        with self._lock:
            self._purge(now)
            self._sessions[session.id] = session

    def get(self, session_id: str, now: float) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and now >= session.expires_at:
                del self._sessions[session_id]
                return None
            return session

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
