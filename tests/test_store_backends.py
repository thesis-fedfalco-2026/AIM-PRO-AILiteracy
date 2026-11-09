"""Store guarantees shared by the SQLite and PostgreSQL backends (S02, D13).

Every ``on_both_backends`` case also runs on PostgreSQL when
``ALM_TEST_POSTGRES_URL`` is set. Data is synthetic; the only network use is the
configured local PostgreSQL test service.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier, Thread
import unittest
from unittest.mock import Mock, patch

from learning.contracts import EntityRef, entity_data
from learning.copy_store import main as copy_main
from learning.store import (LearningStore, RequestRecord, StateConflict, StoreLocation, TableDigest,
                            canonical, copy_store, database_errors, resolve_location)
from tests.learning_fixtures import load_bundle, record, ref
from tests.store_backends import (block_network, new_store_location, on_both_backends, postgres_url,
                                  with_search_path)


TRICKY_TEXT = 'Ünïcödé — 学习 🎓 "quoted" \\ back\\slash\nline sep \u0000 nul \t tab é'
NO_NETWORK = 'Store tests use only the configured PostgreSQL test service'


def in_thread(work):
    """Run ``work`` on its own thread; the result is (thread, outcomes, errors)."""
    outcomes, errors = [], []

    def run():
        try:
            outcomes.append(work())
        except BaseException as error:  # reported to the test thread
            errors.append(error)
    thread = Thread(target=run)
    thread.start()
    return thread, outcomes, errors


class StoreLocationTest(unittest.TestCase):
    def test_backend_is_selected_by_location(self):
        cases = {
            Path('data/state.sqlite'): StoreLocation('sqlite', Path('data/state.sqlite')),
            'data/state.sqlite': StoreLocation('sqlite', Path('data/state.sqlite')),
            'sqlite:///data/state.sqlite': StoreLocation('sqlite', Path('data/state.sqlite')),
            'sqlite:////tmp/state.sqlite': StoreLocation('sqlite', Path('/tmp/state.sqlite')),
            'postgresql://alm@127.0.0.1:5432/alm': StoreLocation('postgresql', 'postgresql://alm@127.0.0.1:5432/alm'),
            'postgres://alm@db/alm': StoreLocation('postgresql', 'postgres://alm@db/alm'),
        }
        for location, expected in cases.items():
            with self.subTest(location=location):
                self.assertEqual(resolve_location(location), expected)
        for location in ('sqlite://', 'sqlite:///', 'sqlite://host/state.sqlite', 'mysql://alm@db/alm'):
            with self.subTest(location=location), self.assertRaises(ValueError):
                resolve_location(location)

    def test_cli_keeps_store_urls_intact(self):
        from learning.__main__ import parse_args
        url = with_search_path('postgresql://alm@127.0.0.1:5432/alm', 'alm_test_x')
        args = parse_args(['--db', url, '--policy', 'policy.json', '--subject', 'admin', '--context', 'c', 'show'])
        self.assertEqual(resolve_location(args.db), StoreLocation('postgresql', url))

    def test_cli_reports_backend_errors_generically(self):
        import psycopg
        from learning.__main__ import main
        self.assertIn(psycopg.Error, database_errors())
        self.assertIn(sqlite3.Error, database_errors())
        with TemporaryDirectory() as directory:
            policy = Path(directory) / 'policy.json'
            policy.write_text(json.dumps({'policy_ref': ref('PolicySet', 'policy')}))
            trusted = Mock(policy_ref=Mock(type='PolicySet'))
            with (patch('learning.__main__.TrustedPolicy.model_validate', return_value=trusted),
                  patch('learning.__main__.LearningStore', side_effect=psycopg.OperationalError('PRIVATE detail')),
                  redirect_stderr(StringIO()) as errors):
                self.assertEqual(main(['--db', 'postgresql://alm@127.0.0.1/alm', '--policy', str(policy),
                                       '--subject', 'admin', '--context', 'c', 'show']), 2)
        self.assertNotIn('PRIVATE', errors.getvalue())


@on_both_backends
class StoreBackendParityTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.location = new_store_location(self, self.temp.name, 'state.sqlite')
        self.store = LearningStore(self.location); self.addCleanup(self.store.close)
        self.store.seed(load_bundle(), owner='session')

    def open(self):
        return LearningStore(self.location)

    def participant(self, version):
        learner = self.store.read(EntityRef(**ref('Participant', 'learner')), owner='session')
        return record('Participant', 'learner', learner.fields, version)

    def test_canonical_payload_bytes_round_trip(self):
        topic = record('Topic', 'unicode-topic', {'name': TRICKY_TEXT, 'definition': TRICKY_TEXT[::-1]})
        self.store.seed((topic,), owner='session')
        payload = canonical({'text': TRICKY_TEXT, 'number': 12345678901234567890, 'nested': [1.5, None, True]})
        self.store.claim_request('bytes', 'session', payload)
        self.store.finish_request('bytes', 'session', {'content': TRICKY_TEXT})
        expected = canonical(entity_data(topic)).encode()
        with self.open() as reopened:
            stored = reopened.db.execute('SELECT payload FROM entities WHERE id=?', (topic.id,)).fetchone()[0]
            self.assertEqual(stored.encode(), expected)
            self.assertEqual(canonical(entity_data(reopened.read(topic.ref, owner='session'))).encode(), expected)
            self.assertEqual(reopened.request_record('bytes', 'session'),
                             RequestRecord(payload, canonical({'content': TRICKY_TEXT})))

    def test_write_transactions_are_serialized_and_read_the_latest_commit(self):
        def writer():
            with self.open() as other, other.write_transaction():
                seen = other.request_record('first', 'session')
                other.reserve_request('second', 'session', 'payload-2')
                return seen
        with self.store.write_transaction():
            self.store.reserve_request('first', 'session', 'payload-1')
            thread, outcomes, errors = in_thread(writer)
            thread.join(0.5)
            self.assertTrue(thread.is_alive(), 'A second writer must wait for the write lock')
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(outcomes, [RequestRecord('payload-1', None)])
        self.assertEqual([r.payload for r in self.store.requests('session')], ['payload-2', 'payload-1'])

    def test_read_transaction_keeps_one_snapshot(self):
        def writer():
            with self.open() as other:
                return other.claim_request('late', 'session', 'payload')
        with self.store.read_transaction():
            self.assertIsNone(self.store.request_record('late', 'session'))
            thread, outcomes, errors = in_thread(writer)
            thread.join(0.5)
            self.assertIsNone(self.store.request_record('late', 'session'))
        thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual((outcomes, errors), ([None], []))
        self.assertEqual(self.store.request_record('late', 'session'), RequestRecord('payload', None))

    def test_versions_are_immutable(self):
        topic = self.store.read(EntityRef(**ref('Topic', 'topic')), owner='session')
        changes = self.store.db.total_changes
        self.store.seed((topic,), owner='session')
        self.assertEqual(self.store.db.total_changes, changes)
        changed = topic.model_copy(update={'fields': {**topic.fields, 'name': 'Rewritten'}})
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.store.seed((changed,), owner='session')
        self.assertEqual(self.store.read(topic.ref, owner='session'), topic)

    def test_owned_returns_the_latest_insertion_not_the_highest_version(self):
        for version in ('9', '10', '2'):
            self.store.seed((self.participant(version),), owner='session')
        self.assertEqual([e.version for e in self.store.owned('session', 'Participant')], ['2'])
        self.assertEqual([e.version for e in self.store.history('session') if e.type == 'Participant'],
                         ['1', '10', '2', '9'])

    def test_request_orders(self):
        with self.store.write_transaction():
            for request_id in ('b', 'a', 'c', 'B'):
                self.store.reserve_request(request_id, 'session', 'payload-' + request_id)
        for request_id in ('c', 'a', 'B'):
            self.store.finish_request(request_id, 'session', {'id': request_id})
        self.assertEqual([r.payload for r in self.store.requests('session')],
                         ['payload-B', 'payload-c', 'payload-a', 'payload-b'])
        # Pinned by id (code point order), the order the SQLite primary key index already gave.
        self.assertEqual([r.payload for r in self.store.recorded_requests('session')],
                         ['payload-B', 'payload-a', 'payload-c'])

    def test_text_order_is_by_code_point(self):
        identities = ('b', 'B', 'a-b', 'a:b', 'a_b', 'é', 'Z', 'a b', 'a')
        proposal = EntityRef(**ref('ChangeProposal', 'ordering'))
        self.store.append_candidates(proposal, tuple(
            record('Topic', identity, {'name': identity, 'definition': 'Ordering probe'}) for identity in identities))
        self.assertEqual([e.id for e in self.store.candidates(proposal)], sorted(identities))

    def test_atomic_scope_keeps_the_sqlite_transaction_model(self):
        with self.store.atomic():
            self.assertFalse(self.store.in_transaction)
            self.store.reserve_request('implicit', 'session', 'payload')
            self.assertTrue(self.store.in_transaction)
        self.assertFalse(self.store.in_transaction)
        # Chat 09 finding 2, kept as is: an atomic scope inside a transaction
        # commits that transaction when it exits.
        with self.store.write_transaction():
            self.store.reserve_request('outer', 'session', 'payload')
            with self.store.atomic():
                self.store.reserve_request('inner', 'session', 'payload')
            self.assertFalse(self.store.in_transaction)
        with self.open() as reopened:
            for request_id in ('implicit', 'outer', 'inner'):
                self.assertEqual(reopened.request_record(request_id, 'session'), RequestRecord('payload', None))

    def test_failed_write_transaction_leaves_nothing(self):
        with self.assertRaises(RuntimeError), self.store.write_transaction():
            self.store.reserve_request('failed', 'session', 'payload')
            raise RuntimeError('Injected failure')
        self.assertFalse(self.store.in_transaction)
        with self.open() as reopened:
            self.assertIsNone(reopened.request_record('failed', 'session'))

    def test_nested_write_transaction_is_refused(self):
        with self.assertRaises(database_errors()), self.store.write_transaction(), self.store.write_transaction():
            pass

    def test_concurrent_identical_requests_record_one_result(self):
        barrier = Barrier(4)

        def claim():
            with self.open() as store:
                barrier.wait(timeout=10)
                try:
                    return store.claim_request('same', 'session', 'payload')
                except StateConflict:
                    return 'pending'
        workers = [in_thread(claim) for _ in range(4)]
        for thread, _, _ in workers:
            thread.join(20)
        self.assertEqual([e for _, _, errors in workers for e in errors], [])
        self.assertEqual(sorted(map(str, (o for _, outcomes, _ in workers for o in outcomes))),
                         ['None', 'pending', 'pending', 'pending'])
        self.store.finish_request('same', 'session', {'content': 'done'})
        self.assertEqual(self.store.claim_request('same', 'session', 'payload'), {'content': 'done'})
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM requests WHERE id='same'").fetchone()[0], 1)

    def test_concurrent_first_open_creates_one_schema(self):
        location = new_store_location(self, self.temp.name, 'fresh.sqlite')
        barrier = Barrier(3)

        def first_open(request_id):
            def run():
                barrier.wait(timeout=10)
                with LearningStore(location) as store:
                    return store.claim_request(request_id, 'session', 'payload')
            return run
        workers = [in_thread(first_open(str(index))) for index in range(3)]
        for thread, _, _ in workers:
            thread.join(20)
        self.assertEqual([e for _, _, errors in workers for e in errors], [])
        with LearningStore(location) as store:
            self.assertEqual({r.payload for r in store.requests('session')}, {'payload'})
            self.assertEqual(len(store.requests('session')), 3)

    def test_table_digests_follow_insertion_order(self):
        empty = self.store.table_digests()
        self.assertEqual(set(empty), {'entities', 'contexts', 'operations', 'requests'})
        self.assertEqual(empty['entities'].rows, len(load_bundle()))
        self.store.claim_request('one', 'session', 'payload')
        digests = self.store.table_digests()
        self.assertEqual(digests['requests'].rows, 1)
        self.assertNotEqual(digests['requests'], empty['requests'])
        self.assertEqual(digests['entities'], empty['entities'])


@unittest.skipUnless(postgres_url(), 'ALM_TEST_POSTGRES_URL is not set')
class PostgreSQLSchemaTest(unittest.TestCase):
    store_backend = 'postgresql'

    def setUp(self):
        block_network(self, NO_NETWORK)
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.location = new_store_location(self, self.temp.name, 'state')

    def test_new_schema_matches_the_logical_tables_and_version(self):
        with LearningStore(self.location) as store:
            self.assertEqual(store.db.execute('SELECT version FROM schema_version').fetchall(), [(2,)])
            keys = store.db.execute("""
                SELECT table_name, string_agg(column_name, ',' ORDER BY ordinal_position)
                FROM information_schema.key_column_usage
                WHERE table_schema=current_schema() AND constraint_name LIKE '%pkey'
                GROUP BY table_name""").fetchall()
            self.assertEqual(dict(keys), {'entities': 'namespace,id,version', 'contexts': 'id',
                                          'operations': 'owner,id', 'requests': 'owner,id'})
            columns = store.db.execute("""
                SELECT table_name, column_name, data_type, collation_name FROM information_schema.columns
                WHERE table_schema=current_schema() ORDER BY table_name, ordinal_position""").fetchall()
        text = {(table, column) for table, column, kind, collation in columns if kind == 'text'}
        self.assertTrue(text and all(collation == 'C' for _, _, kind, collation in columns if kind == 'text'))
        self.assertIn(('entities', 'payload'), text)
        self.assertIn(('entities', 'seq', 'bigint', None), columns)
        self.assertIn(('requests', 'seq', 'bigint', None), columns)

    def test_unversioned_schema_with_tables_is_refused(self):
        with LearningStore(self.location) as store:
            store.db.execute('DROP TABLE schema_version')
            store.reserve_request('kept', 'session', 'payload')
            store.db.commit()
        with self.assertRaisesRegex(ValueError, 'Unversioned'):
            LearningStore(self.location)
        with self.assertRaisesRegex(ValueError, 'Unversioned'):
            LearningStore(self.location)

    def test_unsupported_version_is_refused(self):
        with LearningStore(self.location) as store:
            store.db.execute('UPDATE schema_version SET version=3')
            store.db.commit()
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            LearningStore(self.location)

    def test_concurrent_initialization_does_not_reject_newly_created_schema(self):
        from learning import store as module
        execute = module._PostgreSQLConnection.execute
        competed = []

        def interleaved(connection, sql, *args, **kwargs):
            if sql == 'BEGIN IMMEDIATE' and not competed:
                # Finish a competing opener between the unprotected version check and the locked one.
                competed.append(True)
                with patch.object(module._PostgreSQLConnection, 'execute', execute), LearningStore(self.location):
                    pass
            return execute(connection, sql, *args, **kwargs)
        with patch.object(module._PostgreSQLConnection, 'execute', interleaved):
            with LearningStore(self.location) as opened:
                opened.claim_request('req', 'session', 'payload')
        self.assertEqual(competed, [True])
        with LearningStore(self.location) as reopened, self.assertRaises(StateConflict):
            reopened.claim_request('req', 'session', 'payload')

    def test_search_path_must_name_an_existing_schema(self):
        with self.assertRaisesRegex(ValueError, 'schema'):
            LearningStore(with_search_path(postgres_url(), 'alm_test_missing_schema'))


def synthetic_database(path):
    """A SQLite store with every table populated through the store's own methods."""
    with LearningStore(path) as store:
        store.seed(load_bundle(), owner='session')
        context = store.read_context('session')
        updated = record('ExecutionContext', 'session', context.fields, '2')
        change = record('StateChange', 'change', {
            'context': context.ref.model_dump(), 'baseVersion': '1', 'newVersion': '2',
            'cause': context.ref.model_dump(), 'authorizationBasis': 'policy:policy@1',
            'change': 'Update', 'recordedAt': '2026-11-09T12:00:00+00:00'})
        store.commit_change(change, (updated,), expected_version='1', operation_id='op')
        store.append_candidates(EntityRef(**ref('ChangeProposal', 'proposal')), (
            record('Topic', 'candidate', {'name': TRICKY_TEXT, 'definition': 'Synthetic candidate'}),))
        for request_id in ('b', 'a', 'c'):
            store.claim_request(request_id, 'session', canonical({'text': TRICKY_TEXT, 'id': request_id}))
        store.finish_request('a', 'session', {'content': TRICKY_TEXT})
        return store.table_digests()


class CopyStoreRefusalTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source.sqlite'

    def run_cli(self, *arguments):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = copy_main(list(arguments))
        return code, output.getvalue(), errors.getvalue()

    def test_missing_source_is_refused_without_creating_it(self):
        code, output, errors = self.run_cli('--from', str(self.source), '--to', 'postgresql://alm@127.0.0.1/alm')
        self.assertEqual((code, output), (2, ''))
        self.assertIn('Copy not performed', errors)
        self.assertFalse(self.source.exists())

    def test_targets_other_than_postgresql_are_refused(self):
        synthetic_database(self.source)
        target = Path(self.temp.name) / 'target.sqlite'
        for location in (str(target), 'sqlite:///' + str(target)):
            with self.subTest(location=location), self.assertRaisesRegex(ValueError, 'PostgreSQL'):
                copy_store(self.source, location)
        self.assertFalse(target.exists())

    def test_source_that_is_not_a_version_two_store_is_refused(self):
        with sqlite3.connect(self.source) as db:
            db.execute('CREATE TABLE unrelated (id TEXT)')
        with self.assertRaisesRegex(ValueError, 'version 2'):
            copy_store(self.source, 'postgresql://alm@127.0.0.1/alm')


@unittest.skipUnless(postgres_url(), 'ALM_TEST_POSTGRES_URL is not set')
class CopyStoreTest(unittest.TestCase):
    store_backend = 'postgresql'

    def setUp(self):
        block_network(self, NO_NETWORK)
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source.sqlite'
        self.expected = synthetic_database(self.source)
        self.target = new_store_location(self, self.temp.name, 'target')

    def test_copy_reproduces_the_synthetic_database(self):
        self.assertTrue(all(digest.rows for digest in self.expected.values()))
        self.assertEqual(copy_store(self.source, self.target), self.expected)
        proposal = EntityRef(**ref('ChangeProposal', 'proposal'))
        with LearningStore(self.source) as source, LearningStore(self.target) as target:
            self.assertEqual(target.table_digests(), self.expected)
            self.assertEqual(target.read_context('session'), source.read_context('session'))
            for kind in ('ExecutionContext', 'Participant', 'StateChange'):
                self.assertEqual(target.owned('session', kind), source.owned('session', kind))
            self.assertEqual(target.history('session'), source.history('session'))
            self.assertEqual(target.candidates(proposal), source.candidates(proposal))
            self.assertEqual(target.requests('session'), source.requests('session'))
            self.assertEqual(target.recorded_requests('session'), source.recorded_requests('session'))
            self.assertEqual(target.operation_result('op', 'session'), source.operation_result('op', 'session'))
            self.assertEqual(target.claim_request('a', 'session', source.request_record('a', 'session').payload),
                             {'content': TRICKY_TEXT})

    def test_cli_prints_counts_and_hashes_without_the_url(self):
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(copy_main(['--from', str(self.source), '--to', self.target]), 0)
        summary = json.loads(output.getvalue())
        self.assertEqual({table: TableDigest(**digest) for table, digest in summary.items()}, self.expected)
        self.assertNotIn('postgresql', output.getvalue() + errors.getvalue())

    def test_non_empty_target_is_refused_and_unchanged(self):
        copy_store(self.source, self.target)
        with LearningStore(self.target) as target:
            target.claim_request('extra', 'session', 'payload')
            before = target.table_digests()
        with self.assertRaisesRegex(ValueError, 'not empty'):
            copy_store(self.source, self.target)
        with LearningStore(self.target) as target:
            self.assertEqual(target.table_digests(), before)


if __name__ == '__main__':
    unittest.main()
