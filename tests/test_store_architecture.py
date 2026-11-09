"""Core modules reach the database only through ``LearningStore`` methods."""

import ast
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from learning.store import LearningStore, RequestRecord, canonical
from tests.learning_fixtures import load_bundle


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('learning', 'aimpro')
STORE = Path('learning/store.py')
CONNECTION_CALLS = {'execute', 'executemany', 'executescript'}
SQL = re.compile(r'\b(?:SELECT\b.+\bFROM|INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|'
                 r'(?:CREATE|DROP|ALTER)\s+TABLE|BEGIN(?:\s+(?:IMMEDIATE|EXCLUSIVE|DEFERRED))?\s*$|'
                 r'COMMIT\s*$|ROLLBACK\s*$|PRAGMA\s+\w+)', re.DOTALL)


def violations(source, name='<source>'):
    found = []
    for node in ast.walk(ast.parse(source, name)):
        # ``args.db`` is the parsed ``--db`` path option of the CLI, not a connection.
        if (isinstance(node, ast.Attribute) and node.attr == 'db'
                and not (isinstance(node.value, ast.Name) and node.value.id == 'args')):
            found.append((node.lineno, 'database connection attribute .db'))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in CONNECTION_CALLS):
            found.append((node.lineno, node.func.attr + '() call'))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL.search(node.value):
            found.append((node.lineno, 'SQL in string literal'))
    return sorted(found)


def core_modules():
    for package in PACKAGES:
        for path in sorted((ROOT / package).rglob('*.py')):
            relative = path.relative_to(ROOT)
            if relative != STORE and '__pycache__' not in relative.parts:
                yield relative


class StoreArchitectureTest(unittest.TestCase):
    def test_core_modules_use_no_database_connection(self):
        found = [f'{path}:{line}: {reason}' for path in core_modules()
                 for line, reason in violations((ROOT / path).read_text(encoding='utf-8'), str(path))]
        self.assertEqual(found, [], 'Move database access behind LearningStore methods:\n' + '\n'.join(found))

    def test_detector_reports_direct_database_access(self):
        source = '\n'.join((
            'with store.db:',
            "    connection.execute('BEGIN IMMEDIATE')",
            "rows = cursor.executemany(statement, values)",
            "query = 'SELECT payload FROM requests WHERE owner=?'",
            "insert = 'INSERT INTO requests VALUES (?,?,?,NULL)'",
            "update = f'UPDATE requests SET result={value}'",
            "read = 'BEGIN'",
        ))
        self.assertEqual([line for line, _ in violations(source)], [1, 2, 2, 3, 4, 5, 6, 7])

    def test_detector_accepts_store_methods_and_prose(self):
        source = '\n'.join((
            'with store.write_transaction():',
            '    store.reserve_request(request_id, owner, payload)',
            "text = 'Select an exact release Resource from the catalogue'",
            "status = 'Begin the review; update the selection and insert notes later.'",
            "intent = 'SELECT'",
            'store = LearningStore(args.db)',
        ))
        self.assertEqual(violations(source), [])

    def test_store_module_is_excluded_and_scanned_modules_exist(self):
        modules = set(core_modules())
        self.assertNotIn(STORE, modules)
        self.assertTrue({Path('learning/service.py'), Path('aimpro/trace.py')} <= modules)


class StoreTransactionApiTest(unittest.TestCase):
    """The store methods that replace direct connection use in core modules."""

    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.sqlite'
        self.store = LearningStore(self.path); self.addCleanup(self.store.close)
        self.store.seed(load_bundle(), owner='session')

    def other_writer_locked(self):
        with LearningStore(self.path) as other:
            other.db.execute('PRAGMA busy_timeout=0')
            try:
                other.db.execute('BEGIN IMMEDIATE')
            except sqlite3.OperationalError:
                return True
            other.db.rollback()
            return False

    def test_write_transaction_locks_from_the_start_and_commits(self):
        self.assertFalse(self.store.in_transaction)
        with self.store.write_transaction():
            self.assertTrue(self.store.in_transaction)
            self.assertTrue(self.other_writer_locked())
            self.store.reserve_request('req', 'session', 'payload')
        self.assertFalse(self.store.in_transaction)
        self.assertFalse(self.other_writer_locked())
        with LearningStore(self.path) as reopened:
            self.assertEqual(reopened.request_record('req', 'session'), RequestRecord('payload', None))

    def test_write_transaction_rolls_back_on_failure(self):
        with self.assertRaises(RuntimeError), self.store.write_transaction():
            self.store.reserve_request('req', 'session', 'payload')
            raise RuntimeError('Injected failure')
        self.assertFalse(self.store.in_transaction)
        self.assertIsNone(self.store.request_record('req', 'session'))

    def test_read_transaction_and_atomic_scopes(self):
        with self.store.read_transaction():
            self.assertTrue(self.store.in_transaction)
            self.assertTrue(self.store.has_context('session'))
            self.assertFalse(self.store.has_context('missing'))
        self.assertFalse(self.store.in_transaction)
        with self.store.atomic():
            self.assertFalse(self.store.in_transaction)
            self.store.reserve_request('req', 'session', 'payload')
            self.assertTrue(self.store.in_transaction)
        self.assertFalse(self.store.in_transaction)
        with self.assertRaises(RuntimeError), self.store.atomic():
            self.store.reserve_request('other', 'session', 'payload')
            raise RuntimeError('Injected failure')
        self.assertIsNone(self.store.request_record('other', 'session'))

    def test_request_queries(self):
        with self.store.write_transaction():
            for request_id in ('b', 'a', 'c'):
                self.store.reserve_request(request_id, 'session', 'payload-' + request_id)
            self.store.reserve_request('foreign', 'elsewhere', 'payload')
        self.store.finish_request('a', 'session', {'kind': 'ANSWER'})
        self.assertEqual(self.store.request_record('a', 'session'),
                         RequestRecord('payload-a', canonical({'kind': 'ANSWER'})))
        self.assertIsNone(self.store.request_record('a', 'elsewhere'))
        self.assertEqual([r.payload for r in self.store.requests('session')], ['payload-c', 'payload-a', 'payload-b'])
        self.assertEqual(self.store.recorded_requests('session'),
                         (RequestRecord('payload-a', canonical({'kind': 'ANSWER'})),))

    def test_history_lists_every_owned_active_revision_in_order(self):
        history = self.store.history('session')
        self.assertTrue(history)
        self.assertEqual([e.ref for e in history], sorted((e.ref for e in history),
                                                          key=lambda r: (r.type, r.id, r.version)))
        self.assertIn(self.store.read_context('session').ref, {e.ref for e in history})
        self.assertEqual(self.store.history('missing'), ())


if __name__ == '__main__':
    unittest.main()
