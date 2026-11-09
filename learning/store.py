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


class LearningStore:
    def __init__(self, path: Path):
        self.contract = load_contract()
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
                    self.db.execute("INSERT OR IGNORE INTO contexts VALUES (?,?)", (entity.id, entity.version))

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
        rows = self.db.execute("SELECT payload FROM entities WHERE namespace='active' AND owner=? AND type=? ORDER BY rowid DESC",
                               (owner, kind)).fetchall()
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
        rows = self.db.execute("SELECT payload,result FROM requests WHERE owner=? ORDER BY rowid DESC", (owner,))
        return tuple(RequestRecord(row["payload"], row["result"]) for row in rows)

    def recorded_requests(self, owner: str) -> tuple[RequestRecord, ...]:
        """Requests of the owner with a confirmed result."""
        rows = self.db.execute("SELECT payload,result FROM requests WHERE owner=? AND result IS NOT NULL", (owner,))
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
