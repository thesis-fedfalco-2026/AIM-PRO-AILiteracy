"""Jobs store (D14): agent jobs and their events, never in the ALM tables.

A SQLite location is a database file of its own, refused if it holds the ALM
tables; a PostgreSQL location keeps its tables in the ``jobs`` schema. A job is
named by its context and the ALM ``request_id`` of its command, the
idempotency key: the same command under the same id is the same job, another
command under that id is a :class:`StateConflict`. Every status change is
recorded as a ``status`` event in the same transaction; the run's
content-free events of ``agent_system.events`` are ``progress`` events. Both
kinds share one sequence, the cursor of the progress stream.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Literal, NamedTuple

from pydantic import JsonValue

from agent_system.events import Event
from learning.contracts import EntityRef, Record, Text
from learning.store import StateConflict, canonical, resolve_location


SCHEMA = 'jobs'
VERSION = 1
JobStatus = Literal['QUEUED', 'RUNNING', 'PROPOSED', 'REJECTED', 'FAILED', 'ABANDONED']
STATUSES = JobStatus.__args__
FINAL = frozenset({'PROPOSED', 'REJECTED', 'FAILED', 'ABANDONED'})
_COLUMNS = 'seq,context_id,request_id,kind,subject_key,command,status,outcome,created,updated'


class JobRecord(Record):
    """A job as stored: its exact command, its status and, once ended, its outcome."""
    context_id: Text
    request_id: Text
    kind: Text
    subject_key: Text
    command: dict[str, JsonValue]
    status: JobStatus
    proposal_refs: tuple[EntityRef, ...] = ()
    detail: Text | None = None
    created: Text
    updated: Text


class StatusEvent(Record):
    """The data of a ``status`` event: identifiers only, never a command or a message."""
    status: JobStatus
    proposal_refs: tuple[EntityRef, ...] = ()


class JobEvent(NamedTuple):
    """One stored event: ``seq`` is the stream cursor, ``data`` canonical JSON."""
    seq: int
    name: Literal['status', 'progress']
    data: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class JobStore:
    def __init__(self, location: Path | str):
        self.backend, target = resolve_location(location)
        # One connection, used by the worker thread and by the threads its event sink is called from.
        self._lock = RLock()
        if self.backend == 'postgresql':
            import psycopg
            self.db = psycopg.connect(target, autocommit=True, client_encoding='utf8')
            self._prefix = f'"{SCHEMA}".'
        else:
            self.db = sqlite3.connect(target, timeout=5, isolation_level=None, check_same_thread=False)
            self._prefix = ''
        try:
            self._open()
        except Exception:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False

    def close(self) -> None:
        self.db.close()

    # Statements are written with ``?`` placeholders and ``{p}`` before each table name.
    def _execute(self, sql: str, parameters=()):
        sql = sql.replace('{p}', self._prefix)
        if self.backend == 'postgresql':
            sql = sql.replace('?', '%s')
        return self.db.execute(sql, parameters)

    @contextmanager
    def _transaction(self):
        """A write transaction; SQLite takes its write lock at the start, as the ALM store does."""
        with self._lock:
            self._execute('BEGIN' if self.backend == 'postgresql' else 'BEGIN IMMEDIATE')
            try:
                yield
            except BaseException:
                self._execute('ROLLBACK')
                raise
            self._execute('COMMIT')

    def _open(self) -> None:
        if self.backend == 'postgresql':
            self._open_postgresql()
            return
        with self._transaction():
            version = self._execute('PRAGMA user_version').fetchone()[0]
            tables = {row[0] for row in self._execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'entities' in tables or 'requests' in tables:
                raise ValueError('The jobs store is never the ALM database')
            if version == 0 and not tables:
                for statement in (
                    """CREATE TABLE jobs (seq INTEGER PRIMARY KEY, context_id TEXT NOT NULL, request_id TEXT NOT NULL,
                        kind TEXT NOT NULL, subject_key TEXT NOT NULL, command TEXT NOT NULL, status TEXT NOT NULL,
                        outcome TEXT, created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(context_id, request_id))""",
                    'CREATE INDEX jobs_status ON jobs(status, seq)',
                    """CREATE TABLE events (seq INTEGER PRIMARY KEY, job INTEGER NOT NULL REFERENCES jobs(seq),
                        name TEXT NOT NULL, data TEXT NOT NULL)""",
                    'CREATE INDEX events_job ON events(job, seq)',
                    f'PRAGMA user_version={VERSION}',
                ):
                    self._execute(statement)
            elif version != VERSION:
                raise ValueError('Unsupported jobs store version')

    def _open_postgresql(self) -> None:
        with self._transaction():
            # Serialize the creation of the schema between processes that open it together.
            self._execute('SELECT pg_advisory_xact_lock(hashtext(?))', (f'jobs.store:{SCHEMA}',))
            if self._execute('SELECT 1 FROM information_schema.tables WHERE table_schema=? AND table_name=?',
                             (SCHEMA, 'schema_version')).fetchone() is None:
                for statement in (
                    f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"',
                    """CREATE TABLE {p}jobs (seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        context_id TEXT COLLATE "C" NOT NULL, request_id TEXT COLLATE "C" NOT NULL,
                        kind TEXT COLLATE "C" NOT NULL, subject_key TEXT COLLATE "C" NOT NULL,
                        command TEXT COLLATE "C" NOT NULL, status TEXT COLLATE "C" NOT NULL, outcome TEXT COLLATE "C",
                        created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(context_id, request_id))""",
                    'CREATE INDEX jobs_status ON {p}jobs(status, seq)',
                    """CREATE TABLE {p}events (seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                        job BIGINT NOT NULL REFERENCES {p}jobs(seq), name TEXT NOT NULL, data TEXT COLLATE "C" NOT NULL)""",
                    'CREATE INDEX events_job ON {p}events(job, seq)',
                    'CREATE TABLE {p}schema_version (version INTEGER NOT NULL)',
                ):
                    self._execute(statement)
                self._execute('INSERT INTO {p}schema_version VALUES (?)', (VERSION,))
            elif self._execute('SELECT version FROM {p}schema_version').fetchone() != (VERSION,):
                raise ValueError('Unsupported jobs store version')

    def _record(self, row) -> JobRecord:
        _, context_id, request_id, kind, subject_key, command, status, outcome, created, updated = row
        outcome = json.loads(outcome) if outcome else {}
        return JobRecord(context_id=context_id, request_id=request_id, kind=kind, subject_key=subject_key,
                         command=json.loads(command), status=status, created=created, updated=updated, **outcome)

    def _row(self, context_id: str, request_id: str):
        return self._execute(f'SELECT {_COLUMNS} FROM {{p}}jobs WHERE context_id=? AND request_id=?',
                             (context_id, request_id)).fetchone()

    def _status_event(self, seq: int, status: str, proposal_refs=()) -> None:
        data = StatusEvent(status=status, proposal_refs=proposal_refs).model_dump(mode='json')
        self._execute('INSERT INTO {p}events (job,name,data) VALUES (?,?,?)', (seq, 'status', canonical(data)))

    def submit(self, context_id: str, request_id: str, subject_key: str, kind: str,
               command: dict) -> tuple[JobRecord, bool]:
        """Queue a job; ``(job, False)`` when this exact job was already submitted."""
        text = canonical(command)
        with self._transaction():
            now = _now()
            inserted = self._execute(
                'INSERT INTO {p}jobs (context_id,request_id,kind,subject_key,command,status,created,updated) '
                'VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (context_id, request_id) DO NOTHING',
                (context_id, request_id, kind, subject_key, text, 'QUEUED', now, now)).rowcount == 1
            row = self._row(context_id, request_id)
            if inserted:
                self._status_event(row[0], 'QUEUED')
            elif (row[3], row[4], row[5]) != (kind, subject_key, text):
                raise StateConflict('The request id already names another job')
        return self._record(row), inserted

    def get(self, context_id: str, request_id: str) -> JobRecord | None:
        with self._lock:
            row = self._row(context_id, request_id)
        return None if row is None else self._record(row)

    def claim(self) -> JobRecord | None:
        """Start the oldest queued job: ``QUEUED`` → ``RUNNING``, at most once."""
        lock = ' FOR UPDATE SKIP LOCKED' if self.backend == 'postgresql' else ''
        with self._transaction():
            row = self._execute(f"SELECT context_id,request_id FROM {{p}}jobs WHERE status='QUEUED' "
                                f'ORDER BY seq LIMIT 1{lock}').fetchone()
            if row is None:
                return None
            return self._transition(row[0], row[1], {'QUEUED'}, 'RUNNING', (), None)

    def transition(self, context_id: str, request_id: str, current: set[str], status: str, *,
                   proposal_refs: tuple[EntityRef, ...] = (), detail: str | None = None) -> JobRecord | None:
        """Move a job from one of the ``current`` statuses to ``status``; ``None`` if it is in none of them."""
        if status not in STATUSES or status == 'QUEUED' or not set(current) <= set(STATUSES) - FINAL:
            raise ValueError('Invalid job status change')
        with self._transaction():
            return self._transition(context_id, request_id, current, status, proposal_refs, detail)

    def _transition(self, context_id, request_id, current, status, proposal_refs, detail):
        outcome = None
        if status in FINAL:
            outcome = canonical({'proposal_refs': [r.model_dump(mode='json') for r in proposal_refs], 'detail': detail})
        marks = ','.join('?' * len(current))
        changed = self._execute(f'UPDATE {{p}}jobs SET status=?, outcome=?, updated=? '
                                f'WHERE context_id=? AND request_id=? AND status IN ({marks})',
                                (status, outcome, _now(), context_id, request_id, *sorted(current))).rowcount
        if changed != 1:
            return None
        row = self._row(context_id, request_id)
        self._status_event(row[0], status, proposal_refs)
        return self._record(row)

    def add_progress(self, context_id: str, request_id: str, event: Event) -> None:
        """Record a content-free event of the job's run; the event model has refused any content."""
        data = canonical(event.model_dump(mode='json', by_alias=True))
        with self._transaction():
            row = self._row(context_id, request_id)
            if row is None:
                raise ValueError('No such job')
            self._execute('INSERT INTO {p}events (job,name,data) VALUES (?,?,?)', (row[0], 'progress', data))

    def events(self, context_id: str, request_id: str, after: int = 0) -> tuple[JobEvent, ...]:
        """The job's events after the cursor ``after``, oldest first."""
        with self._lock:
            rows = self._execute('SELECT e.seq,e.name,e.data FROM {p}events e JOIN {p}jobs j ON e.job=j.seq '
                                 'WHERE j.context_id=? AND j.request_id=? AND e.seq>? ORDER BY e.seq',
                                 (context_id, request_id, after)).fetchall()
        return tuple(JobEvent(*row) for row in rows)
