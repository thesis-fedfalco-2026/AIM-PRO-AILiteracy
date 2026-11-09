from pathlib import Path
import sqlite3
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from learning.contracts import EntityRef, entity_data
from learning.store import LearningStore, StateConflict, canonical
from tests.learning_fixtures import load_bundle, record, ref
from tests.store_backends import new_store_location, on_both_backends, sqlite_only


@on_both_backends
class StoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = new_store_location(self, self.temp.name, "state.sqlite")
        self.store = LearningStore(self.path); self.addCleanup(self.store.close)
        self.store.seed(load_bundle(), owner="session")

    def change(self, suffix="change", version="2"):
        context = self.store.read_context("session")
        updated = record("ExecutionContext", "session", context.fields, version)
        change = record("StateChange", suffix, {
            "context": context.ref.model_dump(), "baseVersion": "1", "newVersion": version,
            "cause": context.ref.model_dump(), "authorizationBasis": "policy:policy@1",
            "change": "Update", "recordedAt": "2026-10-27T12:00:00+00:00"})
        return change, updated

    def legacy_database(self):
        path = Path(self.temp.name) / "legacy.sqlite"
        db = sqlite3.connect(path)
        self.addCleanup(db.close)
        self.store.db.backup(db)
        with db:
            db.execute("DROP TABLE operations")
            db.execute("DROP TABLE requests")
            db.execute("CREATE TABLE operations (id TEXT PRIMARY KEY, owner TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL)")
            db.execute("CREATE TABLE requests (id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL, result TEXT)")
            db.execute("PRAGMA user_version=1")
        return path, db

    def test_reopen_preserves_exact_versions(self):
        change, updated = self.change()
        self.store.commit_change(change, (updated,), expected_version="1", operation_id="op")
        with LearningStore(self.path) as reopened:
            self.assertEqual(reopened.read_context("session").version, "2")
            self.assertEqual(reopened.read(EntityRef(**ref("ExecutionContext", "session")), owner="session").version, "1")

    def test_candidate_cannot_resolve_as_active(self):
        candidate = record("Topic", "new", {"name": "New", "definition": "Candidate"})
        proposal = EntityRef(**ref("ChangeProposal", "proposal"))
        self.store.append_candidates(proposal, (candidate,))
        with self.assertRaises(ValueError):
            self.store.read(candidate.ref, owner="session")
        self.assertEqual(self.store.read(candidate.ref, owner="session", proposal=proposal), candidate)

    def test_two_writers_one_base(self):
        change, updated = self.change()
        with LearningStore(self.path) as other:
            self.store.commit_change(change, (updated,), expected_version="1", operation_id="op")
            with self.assertRaises(StateConflict):
                other.commit_change(change, (updated,), expected_version="1", operation_id="other")

    def test_retry_does_not_apply_twice(self):
        change, updated = self.change()
        one = self.store.commit_change(change, (updated,), expected_version="1", operation_id="op")
        two = self.store.commit_change(change, (updated,), expected_version="1", operation_id="op")
        self.assertEqual(one, two)
        other, _ = self.change("other", "3")
        with self.assertRaises(StateConflict):
            self.store.commit_change(other, (updated,), expected_version="1", operation_id="op")

    def test_failure_rolls_back_all_rows(self):
        change, updated = self.change()
        bad = record("Topic", "topic", {"name": "Changed", "definition": "Invalid replacement"})
        with self.assertRaises(ValueError):
            self.store.commit_change(change, (updated, bad), expected_version="1", operation_id="op")
        self.assertEqual(self.store.read_context("session").version, "1")
        with self.assertRaises(ValueError):
            self.store.read(updated.ref, owner="session")

    def test_cross_context_owner_is_denied_and_event_does_not_advance_head(self):
        learner = EntityRef(**ref("Participant", "learner"))
        with self.assertRaises(ValueError):
            self.store.read(learner, owner="other")
        event, _ = self.change()
        self.store.record_event("request/event", event)
        self.assertEqual(self.store.read_context("session").version, "1")

    def test_claim_deduplicates_requests(self):
        self.assertIsNone(self.store.claim_request("req", "session", "payload"))
        with self.assertRaises(StateConflict):
            self.store.claim_request("req", "session", "payload")
        self.store.finish_request("req", "session", {"content": "done"})
        self.assertEqual(self.store.claim_request("req", "session", "payload"), {"content": "done"})
        with self.assertRaises(StateConflict):
            self.store.claim_request("req", "session", "different")

    @sqlite_only
    def test_new_database_keys_requests_and_operations_by_owner_then_id(self):
        self.assertEqual(self.store.db.execute("PRAGMA user_version").fetchone()[0], 2)
        for table in ("requests", "operations"):
            columns = self.store.db.execute(f"PRAGMA table_info({table})").fetchall()
            self.assertEqual([column[1] for column in sorted(columns, key=lambda column: column[5]) if column[5]],
                             ["owner", "id"])

    @sqlite_only
    def test_concurrent_initialization_does_not_reject_newly_created_schema(self):
        path = Path(self.temp.name) / "concurrent.sqlite"
        connect = sqlite3.connect

        class InterleavedConnection(sqlite3.Connection):
            def execute(connection, sql, *args, **kwargs):
                if sql.startswith("SELECT 1 FROM sqlite_master") and not connection.in_transaction:
                    # Finish a competing opener between the unprotected version and schema reads.
                    with patch("learning.store.sqlite3.connect", connect), LearningStore(path):
                        pass
                return super().execute(sql, *args, **kwargs)

        with patch("learning.store.sqlite3.connect",
                   side_effect=lambda *args, **kwargs: connect(*args, factory=InterleavedConnection, **kwargs)):
            with LearningStore(path) as opened:
                self.assertEqual(opened.db.execute("PRAGMA user_version").fetchone()[0], 2)
                opened.claim_request("req", "session", "payload")
        with LearningStore(path) as reopened:
            with self.assertRaises(StateConflict):
                reopened.claim_request("req", "session", "payload")

    def test_request_ids_are_independent_across_owners(self):
        self.assertIsNone(self.store.claim_request("shared", "session", "first"))
        self.assertIsNone(self.store.claim_request("shared", "other", "second"))
        self.store.finish_request("shared", "session", {"content": "one"})
        self.store.finish_request("shared", "other", {"content": "two"})
        self.assertEqual(self.store.claim_request("shared", "session", "first"), {"content": "one"})
        self.assertEqual(self.store.claim_request("shared", "other", "second"), {"content": "two"})

    def test_operation_ids_are_independent_across_owners(self):
        other_context = record("ExecutionContext", "other", self.store.read_context("session").fields)
        self.store.seed((other_context,), owner="other")
        first, first_updated = self.change("session-change")
        second = record("StateChange", "other-change", {
            "context": other_context.ref.model_dump(), "baseVersion": "1", "newVersion": "2",
            "cause": other_context.ref.model_dump(), "authorizationBasis": "policy:policy@1",
            "change": "Update", "recordedAt": "2026-10-27T12:00:00+00:00"})
        second_updated = record("ExecutionContext", "other", other_context.fields, "2")
        self.store.commit_change(first, (first_updated,), expected_version="1", operation_id="shared")
        self.store.commit_change(second, (second_updated,), expected_version="1", operation_id="shared")
        self.assertEqual(self.store.operation_result("shared", "session"), first)
        self.assertEqual(self.store.operation_result("shared", "other"), second)

    @sqlite_only
    def test_v1_migration_preserves_data_and_creates_unmodified_backup(self):
        path, db = self.legacy_database()
        path.chmod(0o600)
        change, _ = self.change()
        with db:
            db.execute("INSERT INTO requests VALUES (?,?,?,?)",
                       ("shared", "session", "payload", canonical({"content": "done"})))
            db.execute("INSERT INTO operations VALUES (?,?,?,?)",
                       ("shared", "session", "fingerprint", canonical(entity_data(change))))
        with LearningStore(path) as migrated:
            self.assertEqual(migrated.db.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(migrated.read_context("session").version, "1")
            self.assertEqual(migrated.claim_request("shared", "session", "payload"), {"content": "done"})
            self.assertEqual(migrated.operation_result("shared", "session"), change)
            self.assertIsNone(migrated.claim_request("shared", "other", "other payload"))
        backups = list(path.parent.glob(f"{path.name}.v1*.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        with sqlite3.connect(backups[0]) as backup:
            self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(backup.execute("SELECT payload,result FROM requests WHERE id='shared'").fetchone(),
                             ("payload", canonical({"content": "done"})))
            self.assertEqual(backup.execute("SELECT fingerprint FROM operations WHERE id='shared'").fetchone()[0],
                             "fingerprint")
            self.assertEqual(backup.execute("SELECT version FROM contexts WHERE id='session'").fetchone()[0], "1")

    @sqlite_only
    def test_migration_does_not_overwrite_existing_backup(self):
        path, _ = self.legacy_database()
        existing = path.with_name(path.name + ".v1.bak")
        existing.write_text("keep this backup")
        with LearningStore(path):
            pass
        self.assertEqual(existing.read_text(), "keep this backup")
        self.assertEqual(len(list(path.parent.glob(f"{path.name}.v1*.bak"))), 2)

    @sqlite_only
    def test_unversioned_database_with_tables_is_not_mislabelled_v2(self):
        path, db = self.legacy_database()
        with db:
            db.execute("PRAGMA user_version=0")
            db.execute("INSERT INTO requests VALUES ('req','session','payload',NULL)")
        with self.assertRaises(ValueError):
            LearningStore(path)
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT payload FROM requests WHERE id='req'").fetchone()[0], "payload")

    @sqlite_only
    def test_failed_migration_leaves_v1_database_intact(self):
        path, db = self.legacy_database()
        with db:
            db.execute("INSERT INTO requests VALUES (NULL,'session','payload',NULL)")
        with self.assertRaises(sqlite3.IntegrityError):
            LearningStore(path)
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT id,owner,payload FROM requests").fetchone(),
                         (None, "session", "payload"))
        self.assertEqual(db.execute("SELECT version FROM contexts WHERE id='session'").fetchone()[0], "1")

    def test_abandon_request_records_terminal_result_before_worker_finishes(self):
        self.store.claim_request("req", "session", "payload")
        with LearningStore(self.path) as canceller:
            canceller.abandon_request("req", "session", {"kind": "FAILURE"})
        with self.assertRaises(StateConflict):
            self.store.finish_request("req", "session", {"kind": "ANSWER"})
        self.assertEqual(self.store.claim_request("req", "session", "payload"), {"kind": "FAILURE"})
        with self.assertRaises(StateConflict):
            self.store.abandon_request("req", "session", {"kind": "FAILURE"})

    def test_finish_request_does_not_commit_outer_transaction(self):
        self.store.claim_request("req", "session", "payload")
        self.store.db.execute("BEGIN IMMEDIATE")
        self.store.finish_request("req", "session", {"kind": "ANSWER"})
        self.store.db.rollback()
        with LearningStore(self.path) as reopened:
            with self.assertRaises(StateConflict):
                reopened.claim_request("req", "session", "payload")
