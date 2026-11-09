from __future__ import annotations

import hashlib
import json
import os
from contextlib import closing, contextmanager, nullcontext
from pathlib import Path
import sqlite3
from typing import NamedTuple

from learning.contracts import Entity, EntityRef, entity_data
from learning.metamodel import load_contract, validate_entity


class StateConflict(ValueError):
    """The recorded operation or context base differs from the requested one."""


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class RequestRecord(NamedTuple):
    """A reserved request: its canonical payload and, once confirmed, its canonical result."""
    payload: str
    result: str | None


class StoreLocation(NamedTuple):
    """Backend name (``sqlite`` or ``postgresql``) and its file path or connection URL."""
    backend: str
    target: Path | str


class TableDigest(NamedTuple):
    """Row count and SHA-256 of a table's rows in insertion (or key) order."""
    rows: int
    sha256: str


def resolve_location(location: Path | str) -> StoreLocation:
    """A ``Path``, a file path or ``sqlite:///path`` selects SQLite; ``postgresql://`` selects PostgreSQL.

    As in SQLAlchemy, ``sqlite:///data/state.sqlite`` is relative and
    ``sqlite:////srv/state.sqlite`` absolute.
    """
    if isinstance(location, Path):
        return StoreLocation("sqlite", location)
    text = os.fspath(location)
    scheme, separator, rest = text.partition("://")
    if not separator:
        return StoreLocation("sqlite", Path(text))
    if scheme in ("postgresql", "postgres"):
        return StoreLocation("postgresql", text)
    if scheme == "sqlite" and rest.startswith("/") and len(rest) > 1:
        return StoreLocation("sqlite", Path(rest[1:]))
    raise ValueError("Unsupported learning store location")


def database_errors() -> tuple[type[Exception], ...]:
    """Exception types the store backends raise, for callers that report failures generically."""
    try:
        import psycopg
    except ImportError:
        return (sqlite3.Error,)
    return (sqlite3.Error, psycopg.Error)


# Columns each table copies and hashes; entities and requests keep their insertion order.
TABLES = {
    "entities": ("namespace", "type", "id", "version", "owner", "payload"),
    "contexts": ("id", "version"),
    "operations": ("id", "owner", "fingerprint", "result"),
    "requests": ("id", "owner", "payload", "result"),
}
# The insertion order: SQLite's rowid, PostgreSQL's identity column (D13).
INSERTION = {"sqlite": "rowid", "postgresql": "seq"}
ADD_CONTEXT = {"sqlite": "INSERT OR IGNORE INTO contexts VALUES (?,?)",
               "postgresql": "INSERT INTO contexts VALUES (?,?) ON CONFLICT DO NOTHING"}
POSTGRESQL_SCHEMA = (
    """CREATE TABLE entities (
        namespace TEXT COLLATE "C" NOT NULL, type TEXT COLLATE "C" NOT NULL, id TEXT COLLATE "C" NOT NULL,
        version TEXT COLLATE "C" NOT NULL, owner TEXT COLLATE "C", payload TEXT COLLATE "C" NOT NULL,
        seq BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
        PRIMARY KEY(namespace, id, version))""",
    'CREATE TABLE contexts (id TEXT COLLATE "C" PRIMARY KEY, version TEXT COLLATE "C" NOT NULL)',
    """CREATE TABLE operations (
        id TEXT COLLATE "C" NOT NULL, owner TEXT COLLATE "C" NOT NULL,
        fingerprint TEXT COLLATE "C" NOT NULL, result TEXT COLLATE "C" NOT NULL,
        PRIMARY KEY(owner,id))""",
    """CREATE TABLE requests (
        id TEXT COLLATE "C" NOT NULL, owner TEXT COLLATE "C" NOT NULL,
        payload TEXT COLLATE "C" NOT NULL, result TEXT COLLATE "C",
        seq BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE,
        PRIMARY KEY(owner,id))""",
    "CREATE TABLE schema_version (version INTEGER NOT NULL)",
    "INSERT INTO schema_version VALUES (2)",
)


class _Row(tuple):
    """A result row read by position or by column name, like ``sqlite3.Row``."""

    def __new__(cls, values, names):
        row = super().__new__(cls, values)
        row._names = names
        return row

    def __getitem__(self, key):
        return super().__getitem__(self._names[key] if isinstance(key, str) else key)

    def keys(self):
        return list(self._names)


def _rows(cursor):
    names = {column.name: index for index, column in enumerate(cursor.description or ())}
    return lambda values: _Row(values, names)


class _PostgreSQLConnection:
    """A psycopg 3 connection with the ``sqlite3`` transaction model the store is written for.

    As in ``sqlite3``: statements outside a transaction run in autocommit,
    ``INSERT``/``UPDATE``/``DELETE`` open a transaction implicitly, and the
    connection used as a context manager commits or rolls back whatever is open,
    so every store method keeps its SQLite transaction boundaries. D13: a write
    transaction holds one transaction-scoped advisory lock, taken by
    ``BEGIN IMMEDIATE`` at the start or before an implicit transaction's first
    write, and reads in READ COMMITTED after the lock, so it sees the latest
    commit; ``BEGIN`` opens a REPEATABLE READ snapshot. Like ``timeout=5`` in
    SQLite, a lock wait fails after five seconds. ``?`` placeholders become ``%s``.
    """

    def __init__(self, url: str):
        import psycopg
        self._psycopg = psycopg
        self.connection = psycopg.connect(url, autocommit=True, row_factory=_rows, client_encoding="utf8")
        try:
            self.connection.execute("SET lock_timeout = '5s'")
            schema, encoding = self.connection.execute(
                "SELECT current_schema(), current_setting('server_encoding')").fetchone()
            if schema is None:
                raise ValueError("PostgreSQL search_path names no existing schema")
            if encoding != "UTF8":
                raise ValueError("PostgreSQL learning database must use UTF8 encoding")
        except Exception:
            self.connection.close()
            raise
        # One store per schema: its write lock does not serialize stores in other schemas.
        self._lock_key = int.from_bytes(hashlib.sha256(f"learning.store:{schema}".encode()).digest()[:8],
                                        "big", signed=True)
        self._locked = False
        self.total_changes = 0

    @property
    def in_transaction(self) -> bool:
        status = self.connection.info.transaction_status
        return status in (self._psycopg.pq.TransactionStatus.INTRANS, self._psycopg.pq.TransactionStatus.INERROR)

    def execute(self, sql: str, parameters=()):
        statement = sql.strip().upper()
        if statement == "BEGIN IMMEDIATE":
            return self._begin("READ COMMITTED", lock=True)
        if statement == "BEGIN":
            return self._begin("REPEATABLE READ", lock=False)
        write = statement.split(None, 1)[0] in ("INSERT", "UPDATE", "DELETE")
        if write:
            if not self.in_transaction:
                self._begin("READ COMMITTED", lock=False)
            if not self._locked:
                self._lock()
        if parameters:
            cursor = self.connection.execute(sql.replace("%", "%%").replace("?", "%s"), parameters)
        else:
            cursor = self.connection.execute(sql)
        if write:
            self.total_changes += max(cursor.rowcount, 0)
        return cursor

    def _begin(self, isolation: str, *, lock: bool):
        if self.in_transaction:
            raise self._psycopg.errors.ActiveSqlTransaction("cannot start a transaction within a transaction")
        cursor = self.connection.execute("BEGIN ISOLATION LEVEL " + isolation)
        self._locked = False
        if lock:
            self._lock()
        return cursor

    def _lock(self):
        self.connection.execute("SELECT pg_advisory_xact_lock(%s)", (self._lock_key,))
        self._locked = True

    def commit(self):
        status = self.connection.info.transaction_status
        self._locked = False
        if status == self._psycopg.pq.TransactionStatus.INERROR:
            self.connection.execute("ROLLBACK")
            raise self._psycopg.errors.InFailedSqlTransaction("transaction failed earlier and was rolled back")
        if status == self._psycopg.pq.TransactionStatus.INTRANS:
            self.connection.execute("COMMIT")

    def rollback(self):
        self._locked = False
        if self.in_transaction:
            self.connection.execute("ROLLBACK")

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, *_):
        if kind is None:
            try:
                self.commit()
            except BaseException:
                self.rollback()
                raise
        else:
            self.rollback()
        return False


class LearningStore:
    def __init__(self, location: Path | str):
        self.contract = load_contract()
        self.backend, path = resolve_location(location)
        if self.backend == "postgresql":
            self.db = _PostgreSQLConnection(path)
            try:
                self._open_postgresql()
            except Exception:
                self.close()
                raise
            return
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                with self.db:
                    self.db.execute("BEGIN IMMEDIATE")
                    version = self.db.execute("PRAGMA user_version").fetchone()[0]
                    if version == 0:
                        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
                            raise ValueError("Unversioned learning database contains tables")
                        for statement in (
                            """CREATE TABLE entities (
                                namespace TEXT NOT NULL, type TEXT NOT NULL, id TEXT NOT NULL,
                                version TEXT NOT NULL, owner TEXT, payload TEXT NOT NULL,
                                PRIMARY KEY(namespace, id, version))""",
                            "CREATE TABLE contexts (id TEXT PRIMARY KEY, version TEXT NOT NULL)",
                            """CREATE TABLE operations (
                                id TEXT NOT NULL, owner TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL,
                                PRIMARY KEY(owner,id))""",
                            """CREATE TABLE requests (
                                id TEXT NOT NULL, owner TEXT NOT NULL, payload TEXT NOT NULL, result TEXT,
                                PRIMARY KEY(owner,id))""",
                            "PRAGMA user_version=2",
                        ):
                            self.db.execute(statement)
                        version = 2
            if version == 1:
                self._migrate_v1(Path(path))
            elif version != 2:
                raise ValueError("Unsupported learning database version")
        except Exception:
            self.close()
            raise

    def _open_postgresql(self) -> None:
        version = self._postgresql_version()
        if version is None:
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                version = self._postgresql_version()
                if version is None:
                    if self.db.execute("SELECT 1 FROM information_schema.tables "
                                       "WHERE table_schema=current_schema() LIMIT 1").fetchone():
                        raise ValueError("Unversioned learning database contains tables")
                    for statement in POSTGRESQL_SCHEMA:
                        self.db.execute(statement)
                    version = 2
        if version != 2:
            raise ValueError("Unsupported learning database version")

    def _postgresql_version(self) -> int | None:
        if self.db.execute("SELECT 1 FROM information_schema.tables "
                           "WHERE table_schema=current_schema() AND table_name='schema_version'").fetchone() is None:
            return None
        row = self.db.execute("SELECT version FROM schema_version").fetchone()
        return None if row is None else row[0]

    def _migrate_v1(self, path: Path) -> None:
        index = 0
        while True:
            backup = path.with_name(path.name + f".v1{'.' + str(index) if index else ''}.bak")
            try:
                os.close(os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
                break
            except FileExistsError:
                index += 1
        try:
            with closing(sqlite3.connect(backup)) as destination:
                self.db.backup(destination)
        except Exception:
            backup.unlink()
            raise
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("""CREATE TABLE operations_v2 (
                id TEXT NOT NULL, owner TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL,
                PRIMARY KEY(owner,id))""")
            self.db.execute("INSERT INTO operations_v2 SELECT id,owner,fingerprint,result FROM operations")
            self.db.execute("""CREATE TABLE requests_v2 (
                id TEXT NOT NULL, owner TEXT NOT NULL, payload TEXT NOT NULL, result TEXT,
                PRIMARY KEY(owner,id))""")
            self.db.execute("INSERT INTO requests_v2 SELECT id,owner,payload,result FROM requests")
            self.db.execute("DROP TABLE operations")
            self.db.execute("DROP TABLE requests")
            self.db.execute("ALTER TABLE operations_v2 RENAME TO operations")
            self.db.execute("ALTER TABLE requests_v2 RENAME TO requests")
            self.db.execute("PRAGMA user_version=2")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.db.close()

    @property
    def in_transaction(self) -> bool:
        return self.db.in_transaction

    @contextmanager
    def write_transaction(self):
        """Hold the database write lock from the start; commit on success, roll back on failure."""
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            yield

    @contextmanager
    def read_transaction(self):
        """Read one consistent snapshot; the first write would still need the write lock."""
        with self.db:
            self.db.execute("BEGIN")
            yield

    @contextmanager
    def atomic(self):
        """Commit on success, roll back on failure; the transaction starts at the first write."""
        with self.db:
            yield

    def _put(self, entity: Entity, owner: str | None, namespace: str = "active"):
        entity = validate_entity(entity_data(entity), self.contract)
        if self.contract.entity_types[entity.type]["instanceLayer"] == "domain_configuration":
            owner = None
        elif entity.type == "ExecutionContext":
            owner = entity.id
        elif "context" in entity.fields:
            record_owner = entity.fields["context"]["id"]
            if owner is not None and owner != record_owner:
                raise ValueError("Entity belongs to another context")
            owner = record_owner
        elif owner is None:
            raise ValueError("State entity requires an owner")
        other = self.db.execute("SELECT type FROM entities WHERE id=? AND type<>? LIMIT 1",
                                (entity.id, entity.type)).fetchone()
        if other:
            raise ValueError("Entity identity cannot change type")
        payload = canonical(entity_data(entity))
        old = self.db.execute("SELECT owner,payload FROM entities WHERE namespace=? AND id=? AND version=?",
                              (namespace, entity.id, entity.version)).fetchone()
        if old:
            if old["payload"] != payload or old["owner"] != owner:
                raise ValueError("Entity version is immutable")
            return
        self.db.execute("INSERT INTO entities VALUES (?,?,?,?,?,?)",
                        (namespace, entity.type, entity.id, entity.version, owner, payload))

    def seed(self, entities: tuple[Entity, ...], *, owner: str | None = None):
        """Internal bootstrap primitive; callers must validate administrative authority."""
        with self.atomic():
            for entity in entities:
                self._put(entity, owner)
                if entity.type == "ExecutionContext":
                    self.db.execute(ADD_CONTEXT[self.backend], (entity.id, entity.version))

    def read(self, ref: EntityRef, *, owner: str | None, proposal: EntityRef | None = None) -> Entity:
        namespace = "active" if proposal is None else canonical(proposal.model_dump())
        row = self.db.execute("SELECT owner,payload FROM entities WHERE namespace=? AND type=? AND id=? AND version=?",
                              (namespace, ref.type, ref.id, ref.version)).fetchone()
        if row is None or (row["owner"] is not None and row["owner"] != owner):
            raise ValueError("Reference unavailable in this context")
        return validate_entity(json.loads(row["payload"]), self.contract)

    def has_context(self, context_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM contexts WHERE id=?", (context_id,)).fetchone() is not None

    def read_context(self, context_id: str) -> Entity:
        row = self.db.execute("SELECT version FROM contexts WHERE id=?", (context_id,)).fetchone()
        if row is None:
            raise ValueError("Context unavailable")
        return self.read(EntityRef(type="ExecutionContext", id=context_id, version=row[0]), owner=context_id)

    def owned(self, owner: str, kind: str) -> tuple[Entity, ...]:
        rows = self.db.execute("SELECT payload FROM entities WHERE namespace='active' AND owner=? AND type=? "
                               f"ORDER BY {INSERTION[self.backend]} DESC", (owner, kind)).fetchall()
        latest = {}
        for row in rows:
            entity = validate_entity(json.loads(row[0]), self.contract)
            latest.setdefault(entity.id, entity)
        return tuple(latest.values())

    def history(self, owner: str) -> tuple[Entity, ...]:
        """Every active revision the owner holds, ordered by type, id and version."""
        rows = self.db.execute("SELECT payload FROM entities WHERE namespace='active' AND owner=? ORDER BY type,id,version",
                               (owner,)).fetchall()
        return tuple(validate_entity(json.loads(row[0]), self.contract) for row in rows)

    def candidates(self, proposal: EntityRef) -> tuple[Entity, ...]:
        rows = self.db.execute("SELECT payload FROM entities WHERE namespace=? ORDER BY id,version",
                               (canonical(proposal.model_dump()),)).fetchall()
        return tuple(validate_entity(json.loads(row[0]), self.contract) for row in rows)

    def append_candidates(self, proposal: EntityRef, entities: tuple[Entity, ...]) -> None:
        with self.atomic():
            for entity in entities:
                owner = entity.fields.get("context", {}).get("id")
                self._put(entity, owner, canonical(proposal.model_dump()))

    def record_event(self, request_id: str, event: Entity) -> Entity:
        owner = event.fields["context"]["id"]
        with self.atomic():
            self._put(event, owner)
        return event

    def operation_result(self, operation_id: str, owner: str) -> Entity | None:
        row = self.db.execute("SELECT result FROM operations WHERE id=? AND owner=?", (operation_id, owner)).fetchone()
        return None if row is None else validate_entity(json.loads(row[0]), self.contract)

    def commit_change(self, change: Entity, entities: tuple[Entity, ...], *, expected_version: str,
                      operation_id: str, precondition=None) -> Entity:
        owner = change.fields["context"]["id"]
        fingerprint = hashlib.sha256(canonical([entity_data(change), [entity_data(e) for e in entities],
                                                 expected_version]).encode()).hexdigest()
        with self.write_transaction():
            old = self.db.execute("SELECT * FROM operations WHERE owner=? AND id=?", (owner, operation_id)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint:
                    raise StateConflict("Operation identity has different content")
                return validate_entity(json.loads(old["result"]), self.contract)
            current = self.read_context(owner)
            if current.version != expected_version or change.fields["baseVersion"] != expected_version:
                raise StateConflict("Context revision has changed")
            if precondition is not None:
                precondition()
            new_version = change.fields["newVersion"]
            if new_version == expected_version or not any(
                e.type == "ExecutionContext" and e.id == owner and e.version == new_version for e in entities
            ):
                raise ValueError("Change requires a new context revision")
            for entity in entities:
                self._put(entity, owner)
            self._put(change, owner)
            self.db.execute("UPDATE contexts SET version=? WHERE id=?", (new_version, owner))
            self.db.execute("INSERT INTO operations VALUES (?,?,?,?)",
                            (operation_id, owner, fingerprint, canonical(entity_data(change))))
        return change

    def claim_request(self, request_id: str, owner: str, payload: str) -> dict | None:
        with self.write_transaction():
            row = self.db.execute("SELECT * FROM requests WHERE owner=? AND id=?", (owner, request_id)).fetchone()
            if row:
                if row["payload"] != payload or row["result"] is None:
                    raise StateConflict("Request conflicts or has no confirmed result")
                return json.loads(row["result"])
            self.reserve_request(request_id, owner, payload)
        return None

    def reserve_request(self, request_id: str, owner: str, payload: str) -> None:
        """Record a pending request inside the caller's write transaction."""
        self.db.execute("INSERT INTO requests VALUES (?,?,?,NULL)", (request_id, owner, payload))

    def request_record(self, request_id: str, owner: str) -> RequestRecord | None:
        row = self.db.execute("SELECT payload,result FROM requests WHERE owner=? AND id=?",
                              (owner, request_id)).fetchone()
        return None if row is None else RequestRecord(row["payload"], row["result"])

    def requests(self, owner: str) -> tuple[RequestRecord, ...]:
        """Every request of the owner, newest reservation first."""
        rows = self.db.execute(f"SELECT payload,result FROM requests WHERE owner=? ORDER BY {INSERTION[self.backend]} DESC",
                               (owner,))
        return tuple(RequestRecord(row["payload"], row["result"]) for row in rows)

    def recorded_requests(self, owner: str) -> tuple[RequestRecord, ...]:
        """Requests of the owner with a confirmed result, by request id."""
        rows = self.db.execute("SELECT payload,result FROM requests WHERE owner=? AND result IS NOT NULL ORDER BY id",
                               (owner,))
        return tuple(RequestRecord(row["payload"], row["result"]) for row in rows)

    def request_result(self, request_id: str, owner: str, payload: str) -> dict | None:
        row = self.db.execute("SELECT payload,result FROM requests WHERE owner=? AND id=?",
                              (owner, request_id)).fetchone()
        if row is None:
            return None
        if row["payload"] != payload or row["result"] is None:
            raise StateConflict("Request conflicts or has no confirmed result")
        return json.loads(row["result"])

    def finish_request(self, request_id: str, owner: str, result: dict):
        with nullcontext() if self.in_transaction else self.atomic():
            cursor = self.db.execute("UPDATE requests SET result=? WHERE id=? AND owner=? AND result IS NULL",
                                     (canonical(result), request_id, owner))
            if cursor.rowcount != 1:
                raise StateConflict("Request is not pending")

    def abandon_request(self, request_id: str, owner: str, result: dict):
        self.finish_request(request_id, owner, result)

    def table_digests(self) -> dict[str, TableDigest]:
        """Row count and SHA-256 of every table, as the copy tool verifies them."""
        return _table_digests(self.db, self.backend)


def _table_digests(db, backend: str) -> dict[str, TableDigest]:
    digests = {}
    for table, columns in TABLES.items():
        digest, count = hashlib.sha256(), 0
        for row in db.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY {_copy_order(backend, table)}"):
            digest.update(canonical(list(row)).encode() + b"\n")
            count += 1
        digests[table] = TableDigest(count, digest.hexdigest())
    return digests


def _copy_order(backend: str, table: str) -> str:
    return {"entities": INSERTION[backend], "requests": INSERTION[backend],
            "contexts": "id", "operations": "owner,id"}[table]


def _read_sqlite_source(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise ValueError("Source learning database file not found")
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
    try:
        if db.execute("PRAGMA user_version").fetchone()[0] != 2:
            raise ValueError("Source is not a version 2 learning database")
    except Exception:
        db.close()
        raise
    return db


def copy_store(source: Path | str, target: str) -> dict[str, TableDigest]:
    """Copy a SQLite store into an empty PostgreSQL store; return the verified table digests.

    The source is opened read-only and read in one snapshot. Rows are written in
    one target write transaction, in insertion order, and committed only when the
    target's row counts and SHA-256 digests equal the source's.
    """
    origin, destination = resolve_location(source), resolve_location(target)
    if origin.backend != "sqlite" or destination.backend != "postgresql":
        raise ValueError("The copy runs from a SQLite file to a PostgreSQL URL")
    with closing(_read_sqlite_source(origin.target)) as db, LearningStore(destination.target) as store:
        with db:
            db.execute("BEGIN")
            expected = _table_digests(db, "sqlite")
            with store.write_transaction():
                if any(store.db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in TABLES):
                    raise ValueError("Target store is not empty")
                for table, columns in TABLES.items():
                    insert = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' * len(columns))})"
                    rows = db.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY {_copy_order('sqlite', table)}")
                    for row in rows:
                        store.db.execute(insert, tuple(row))
                copied = _table_digests(store.db, "postgresql")
                if copied != expected:
                    raise ValueError("Copied rows differ from the source; nothing was committed")
    return copied
