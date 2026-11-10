"""Source discovery (S09a2): the model-free search that a source plan is chosen from.

A teacher cannot name exact excerpts before searching. Discovery runs the
teacher's queries in the PREPARATION scope and records what they found in the
host requests store, under the request id; a replay returns it without a new
search. The teacher then picks excerpts from it for the source plan of the
preparation (``prepare_sources``), which runs the same queries again and
fetches the exact excerpts.
"""

import copy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from aimpro.audit import DEFAULT_PROJECT
from aimpro.source_selection import SourceDiscovery, SourcePlan
from aimpro.source_service import DiscoveredSources, PreparedSources
from learning.metamodel import load_contract
from learning.policies import ScopeGrant
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from tests.syllabus_fixtures import source
from tests.test_aimpro_retrieval import response
from tests.test_learning_context import policy


def discovery(*queries):
    return SourceDiscovery(source_scope='wp3', queries=tuple({'query': q, 'k': 3} for q in queries or
                                                             ('prompting', 'prompt clarity')))


def other_document():
    doc = copy.deepcopy(response()['documents'][0])
    doc.update(id='chunk-2', text='A second synthetic excerpt about tone.')
    return doc


class SourceDiscoveryTest(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(target, side_effect=AssertionError('Source discovery tests must stay offline'))
            blocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(blocked.assert_not_called)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'sources.sqlite'
        self.store = LearningStore(self.path)
        self.addCleanup(self.store.close)
        trusted = policy().model_copy(update={'scopes': {
            'wp3': ScopeGrant(contexts=['session'], subjects=['admin'], sources=['wp3'])}})
        self.service = LearningService(self.store, load_contract(), trusted, Mock())
        self.root = self.service.bootstrap('session', 'admin')
        self.client = Mock()
        self.client.search.side_effect = [response(), {'documents': [response()['documents'][0], other_document()],
                                                       'truncated': False}]
        self.client_factory = Mock(return_value=self.client)

    def discover(self, request_id='discovery', value=None, subject='admin'):
        return self.service.discover_aimpro_syllabus_sources('session', subject, value or discovery(),
            request_id=request_id, search_client_factory=self.client_factory)

    def requests(self):
        return self.store.db.execute('SELECT count(*) FROM requests').fetchone()[0]

    def test_discovery_records_every_excerpt_found_and_builds_no_model(self):
        entities = self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0]
        result = self.discover()
        self.assertIsInstance(result, DiscoveredSources)
        self.assertEqual((result.kind, result.subject_key, result.context), ('SOURCE_DISCOVERY', 'admin', self.root.ref))
        self.assertEqual(result.discovery, discovery())
        self.assertEqual([d.query.query for d in result.discoveries], ['prompting', 'prompt clarity'])
        self.assertEqual((result.unique_discovered_documents, result.duplicate_document_hits), (2, 1))
        self.assertEqual([c.kwargs['scope'].mode for c in self.client.search.call_args_list], ['PREPARATION'] * 2)
        self.assertEqual([c.kwargs['scope'].source_scope_keys for c in self.client.search.call_args_list],
                         [('wp3',)] * 2)
        self.client.fetch_preparation_documents.assert_not_called()
        # Only the request record is written: no entity, the context unchanged.
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0], entities)
        self.assertEqual(self.store.read_context('session'), self.root)

    def test_a_replayed_request_id_returns_the_same_discovery_without_a_search(self):
        first = self.discover()
        self.client_factory.side_effect = AssertionError('No repeated search')
        self.assertEqual(self.discover(), first)
        with self.assertRaises(StateConflict):
            self.discover(value=discovery('another query'))

    def test_authorization_and_scope_precede_the_client_and_the_reservation(self):
        for subject, value in (('learner', discovery()),
                               ('admin', discovery().model_copy(update={'source_scope': 'other'}))):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                self.discover(subject=subject, value=value)
        self.client_factory.assert_not_called()
        self.assertEqual(self.requests(), 0)

    def test_invalid_discoveries_are_refused(self):
        for queries in ((), ({'query': 'q', 'k': 3},) * 2, tuple({'query': f'q{i}', 'k': 3} for i in range(21)),
                        ({'query': 'q', 'k': 21},)):
            with self.subTest(queries=queries), self.assertRaises(ValueError):
                SourceDiscovery(source_scope='wp3', queries=queries)

    def test_a_search_that_fails_is_recorded_as_a_failure_without_its_content(self):
        self.client.search.side_effect = [{'documents': [], 'truncated': True}]
        result = self.discover()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(result.content, 'Source discovery did not complete; nothing was recorded for the course.')
        self.client_factory.side_effect = AssertionError('No repeated search')
        self.assertEqual(self.discover(), result)

    def test_discovery_needs_a_preparation_draft_context(self):
        with patch('aimpro.source_service._draft', side_effect=ValueError('Draft required')):
            with self.assertRaises(ValueError):
                self.discover()
        self.client_factory.assert_not_called()
        self.assertEqual(self.requests(), 0)

    def test_a_plan_built_from_the_discovery_prepares_the_chosen_excerpts(self):
        found = self.discover()
        chosen = found.discoveries[1].evidence.resources[0].documents[1]
        resource = found.discoveries[1].evidence.resources[0]
        plan = SourcePlan(source_sha256=source().source.source_sha256, source_scope='wp3',
            queries=found.discovery.queries, documents=({
                'resource_id': resource.identity, 'resource_version': resource.version, 'document_id': chosen.id,
                'content_sha256': hashlib.sha256(chosen.text.encode()).hexdigest(),
                'purpose': 'Tone of a business prompt.', 'limitations': ['Synthetic excerpt.']},))
        self.client.search.side_effect = [response(), {'documents': [response()['documents'][0], other_document()],
                                                       'truncated': False}]
        self.client.fetch_preparation_documents.return_value = {'documents': [other_document()], 'truncated': False}
        prepared = self.service.prepare_aimpro_syllabus_sources('session', 'admin', DEFAULT_PROJECT, plan,
            request_id='preparation', search_client_factory=self.client_factory)
        self.assertIsInstance(prepared, PreparedSources)
        self.assertEqual([d.id for d in prepared.data.corpus_evidence.resources[0].documents], ['chunk-2'])


    def test_the_cli_discovers_without_models(self):
        from contextlib import redirect_stdout
        from io import StringIO
        import json
        from learning.__main__ import main
        directory = self.path.parent
        (directory / 'policy.json').write_text(self.service.policy.model_dump_json())
        (directory / 'discovery.json').write_text(discovery().model_dump_json())
        self.store.close()
        args = ['--db', str(self.path), '--policy', str(directory / 'policy.json'), '--context', 'session',
                '--subject', 'admin', 'discover-aimpro-syllabus-sources', '--discovery', str(directory / 'discovery.json'),
                '--request-id', 'discovery']
        with patch('learning.__main__._aimpro_search_client', self.client_factory), \
             patch('learning.__main__._aimpro_authoring', side_effect=AssertionError('Discovery builds no model')), \
             redirect_stdout(StringIO()) as output:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())['kind'], 'SOURCE_DISCOVERY')


class SourceRecordTest(SourceDiscoveryTest):
    """The completed discovery or preparation of a subject, read back for the teacher's review."""

    def prepare(self, request_id='preparation'):
        doc = response()['documents'][0]
        plan = SourcePlan(source_sha256=source().source.source_sha256, source_scope='wp3',
            queries=({'query': 'prompting', 'k': 3},), documents=({
                'resource_id': doc['metadata']['source'], 'resource_version': 'v1', 'document_id': doc['id'],
                'content_sha256': hashlib.sha256(doc['text'].encode()).hexdigest(),
                'purpose': 'Task, audience and tone.', 'limitations': ['Synthetic excerpt.']},))
        self.client.search.side_effect = None
        self.client.search.return_value = response()
        self.client.fetch_preparation_documents.return_value = response()
        return self.service.prepare_aimpro_syllabus_sources('session', 'admin', DEFAULT_PROJECT, plan,
            request_id=request_id, search_client_factory=self.client_factory)

    def read(self, request_id, kind, subject='admin'):
        return self.service.aimpro_source_request('session', subject, request_id, kind)

    def test_a_completed_discovery_and_preparation_are_read_back_unchanged(self):
        found, prepared = self.discover(), self.prepare()
        self.client_factory.side_effect = AssertionError('Reading searches nothing')
        self.assertEqual(self.read('discovery', 'SOURCE_DISCOVERY'), found)
        self.assertEqual(self.read('preparation', 'SOURCE_PREPARATION'), prepared)

    def test_unknown_failed_other_kinds_and_other_operations_read_as_none(self):
        self.discover()
        self.prepare()
        self.client.search.side_effect = [{'documents': [], 'truncated': True}]
        self.discover('failed')
        self.store.claim_request('pending', 'session', '{}')
        for request_id, kind in (('missing', 'SOURCE_DISCOVERY'), ('failed', 'SOURCE_DISCOVERY'),
                                 ('pending', 'SOURCE_DISCOVERY'), ('discovery', 'SOURCE_PREPARATION'),
                                 ('preparation', 'SOURCE_DISCOVERY')):
            with self.subTest(request_id=request_id, kind=kind):
                self.assertIsNone(self.read(request_id, kind))

    def test_another_subject_cannot_read_a_discovery(self):
        self.discover()
        with self.assertRaises(ValueError):
            self.read('discovery', 'SOURCE_DISCOVERY', subject='learner')


if __name__ == '__main__':
    unittest.main()
