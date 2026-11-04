"""Production selected-source boundaries with synthetic search/model responses."""

import copy
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

from aimpro.audit import DEFAULT_PROJECT
from aimpro.source_selection import SourcePlan, collect_sources
from aimpro.source_service import PreparedSources
from document_search.contracts import PreparationDocumentRef, SearchScope, resource_key
from document_search.postgres import PostgresBackend
from document_search.backend import SearchError
from learning.__main__ import main
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.policies import ScopeGrant
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from tests.syllabus_fixtures import Curator, Reviewer, source
from tests.test_aimpro_retrieval import response
from tests.test_learning_context import policy


def plan(documents=None):
    documents = documents or response()['documents']
    return SourcePlan(source_sha256=source().source.source_sha256, source_scope='wp3',
        queries=({'query': 'prompting', 'k': 3}, {'query': 'prompt clarity', 'k': 3}),
        documents=tuple({'resource_id': d['metadata']['source'],
            'resource_version': json.loads(d['metadata']['resource_key'])[1],
            'document_id': d['id'], 'content_sha256': hashlib.sha256(d['text'].encode()).hexdigest(),
            'purpose': 'Support explicit task, audience and tone.',
            'limitations': ['Synthetic excerpt; not a validated assessment instrument.']} for d in documents))


class SourceSelectionTest(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(target, side_effect=AssertionError('Source selection tests must stay offline'))
            blocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(blocked.assert_not_called)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'sources.sqlite'
        self.store = LearningStore(self.path)
        self.addCleanup(self.store.close)
        trusted = policy().model_copy(update={'scopes': {
            'wp3': ScopeGrant(contexts=['session'], subjects=['admin'], sources=['wp3'])}})
        self.service = LearningService(self.store, load_contract(), trusted, Mock())
        self.root = self.service.bootstrap('session', 'admin')
        self.client = Mock()
        self.client.search.return_value = response()
        self.client.fetch_preparation_documents.return_value = response()
        self.client_factory = Mock(return_value=self.client)
        self.curator, self.reviewer = Curator(), Reviewer()
        self.models = Mock(return_value=(self.curator, self.reviewer, None))

    def prepare(self, request_id='sources', value=None, subject='admin'):
        return self.service.prepare_aimpro_syllabus_sources('session', subject, DEFAULT_PROJECT,
            value or plan(), request_id=request_id, search_client_factory=self.client_factory)

    def generate(self, request_id='selected', prepared_sources='sources', subject='admin'):
        return self.service.generate_aimpro_syllabus('session', subject, DEFAULT_PROJECT,
            request_id=request_id, source_scope='wp3', prepared_sources=prepared_sources,
            authoring_factory=self.models)

    def test_preparation_deduplicates_real_responses_and_never_constructs_models(self):
        before = self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0]
        result = self.prepare()
        self.assertIsInstance(result, PreparedSources)
        self.assertEqual(self.client.search.call_count, 2)
        self.assertEqual(result.trace.unique_discovered_documents, 1)
        self.assertEqual(result.trace.duplicate_document_hits, 1)
        self.assertEqual(result.data.corpus_evidence.selection.trace_sha256, result.trace.digest)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0], before)
        self.assertEqual(self.store.read_context('session'), self.root)
        self.models.assert_not_called()
        self.assertEqual(self.client.fetch_preparation_documents.call_args.kwargs['scope'].mode, 'PREPARATION')

    def test_exact_selection_can_fetch_a_different_excerpt_of_a_discovered_resource(self):
        selected = copy.deepcopy(response()['documents'][0])
        selected.update(id='chunk-2', text='A separate exact synthetic excerpt about a specific audience.')
        self.client.fetch_preparation_documents.return_value = {'documents': [selected], 'truncated': False}
        result = self.prepare(value=plan([selected]))
        self.assertIsInstance(result, PreparedSources)
        self.assertEqual(result.data.corpus_evidence.resources[0].documents[0].id, 'chunk-2')
        self.assertEqual(result.trace.discoveries[0].evidence.resources[0].documents[0].id, 'chunk-1')

    def test_exact_excerpt_whitespace_survives_retrieval_snapshot_and_model_input(self):
        doc = copy.deepcopy(response()['documents'][0])
        doc['text'] = '\n' + doc['text'] + '\n  '
        selected = {'documents': [doc], 'truncated': False}
        self.client.search.return_value = selected
        self.client.fetch_preparation_documents.return_value = selected
        prepared = self.prepare(value=plan([doc]))
        self.assertIsInstance(prepared,PreparedSources)
        excerpt = prepared.data.corpus_evidence.resources[0].documents[0]
        self.assertEqual(excerpt.text,doc['text'])
        self.assertEqual(hashlib.sha256(excerpt.text.encode()).hexdigest(),prepared.trace.plan.documents[0].content_sha256)

    def test_authorization_precedes_source_read_client_creation_and_reservation(self):
        with patch('aimpro.source_service.prepare_input', side_effect=AssertionError('Authorize first')):
            with self.assertRaises(ValueError):
                self.prepare(subject='learner')
        self.client_factory.assert_not_called()
        self.models.assert_not_called()
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE id='sources'").fetchone())
        self.prepare()
        with patch('aimpro.source_service.prepare_input', side_effect=AssertionError('Authorize first')):
            with self.assertRaises(ValueError):
                self.generate(subject='learner')

    def test_invalid_plans_conflicting_documents_and_diversity_limits_are_rejected(self):
        value = plan()
        doc = value.documents[0]
        for update in ({'queries': value.queries * 2}, {'documents': value.documents * 2},
                       {'min_resources': 2}, {'queries': ({'query': 'prompting', 'k': True},)},
                       {'documents': (doc.model_copy(update={'resource_version': 'latest'}),)}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                SourcePlan.model_validate(value.model_copy(update=update).model_dump(mode='json', warnings=False))
        wrong = value.model_copy(update={'source_sha256': 'changed-source'})
        with self.assertRaises(ValueError):
            self.prepare(value=wrong)
        self.client_factory.assert_not_called()

    def test_truncation_scope_metadata_content_and_missing_selection_fail_before_models(self):
        for i, mutate in enumerate((
            lambda r: r.update(truncated=True),
            lambda r: r['documents'][0].update(text='Changed content under the same id'),
            lambda r: r['documents'][0]['metadata'].update(source_scope='other'),
            lambda r: r['documents'][0]['metadata'].update(title='Conflicting title'),
            lambda r: r['documents'][0]['metadata'].update(resource_key=resource_key('wp3:test','v2')),
            lambda r: r.update(documents=[]),
        )):
            result = response(); mutate(result)
            self.client.fetch_preparation_documents.return_value = result
            with self.subTest(case=i):
                self.assertEqual(self.prepare(str(i)).kind, 'FAILURE')
        self.models.assert_not_called()
        self.assertFalse(self.store.owned('session', 'ChangeProposal'))
        self.client.search.side_effect = [response(), {**response(), 'documents': [
            {**response()['documents'][0], 'text': 'A conflicting discovery excerpt'}]}]
        self.assertEqual(self.prepare('conflicting-discovery').kind, 'FAILURE')

    def test_undiscovered_resource_cannot_be_fetched_by_the_plan(self):
        doc = copy.deepcopy(response()['documents'][0])
        doc['metadata'].update(source='wp3:foreign', resource_key=resource_key('wp3:foreign','v1'))
        self.assertEqual(self.prepare(value=plan([doc])).kind, 'FAILURE')
        self.client.fetch_preparation_documents.assert_not_called()

    def test_reservation_precedes_queries_and_external_work_has_no_write_lock(self):
        def search(*args, **kwargs):
            self.assertFalse(self.store.db.in_transaction)
            with LearningStore(self.path) as other:
                with other.db:
                    other.db.execute('BEGIN IMMEDIATE')
                    row = other.db.execute("SELECT payload,result FROM requests WHERE id='sources'").fetchone()
                    self.assertIsNone(row['result'])
                    self.assertIn('source_snapshot', json.loads(row['payload']))
            return response()
        self.client.search.side_effect = search
        self.assertIsInstance(self.prepare(), PreparedSources)
        self.models.side_effect = lambda: (self.assertFalse(self.store.db.in_transaction) or
                                            (self.curator, self.reviewer, None))
        self.assertEqual(self.generate().kind, 'PROPOSAL')

    def test_preparation_and_generation_replay_are_exact_and_reuse_conflicts(self):
        prepared = self.prepare()
        self.client_factory.side_effect = AssertionError('No repeated retrieval')
        self.assertEqual(self.prepare(), prepared)
        with self.assertRaises(StateConflict):
            self.prepare(value=plan().model_copy(update={'max_documents_per_resource': 2}))
        result = self.generate()
        proposal = self.store.read(result.proposal_refs[0], owner='session')
        self.service.decide('session','admin',proposal.ref,'APPROVE','Explicit synthetic decision')
        self.service.apply('session','admin',proposal.ref,'selected')
        self.models.side_effect = AssertionError('No repeated models')
        self.assertEqual(self.generate(), result)
        with self.assertRaises(StateConflict):
            self.generate(prepared_sources='different')

    def test_generation_requires_a_completed_same_context_host_preparation(self):
        with self.assertRaises(ValueError):
            self.generate()
        self.store.claim_request('pending','session','{}')
        with self.assertRaises(ValueError):
            self.generate(prepared_sources='pending')
        self.models.assert_not_called()
        self.prepare()
        root = self.store.read_context('session')
        changed = root.model_copy(update={'version': 'changed'})
        proposal = self.service.propose('session','admin',(root.ref,),(changed,),'Synthetic context edit')
        self.service.decide('session','admin',proposal.ref,'APPROVE','Synthetic review')
        self.service.apply('session','admin',proposal.ref,'changed')
        with self.assertRaises(StateConflict):
            self.generate()
        self.models.assert_not_called()

    def test_source_trace_and_limitation_notes_persist_with_pending_syllabus(self):
        self.prepare()
        result = self.generate()
        self.assertEqual(result.kind, 'PROPOSAL')
        proposal = self.store.read(result.proposal_refs[0], owner='session')
        saved = proposal_candidates(self.store, proposal)
        trace = next(e for e in saved if e.id.endswith(':retrieval-trace'))
        snapshot = next(e for e in saved if e.id.endswith(':source-snapshot'))
        self.assertIn(trace.ref.model_dump(), snapshot.fields['derivedFrom'])
        self.assertEqual(json.loads(trace.fields['contentOrLocator'])['plan'], plan().model_dump(mode='json'))
        prompt = self.curator.calls[0][1]
        self.assertIn('not a validated assessment instrument', prompt)
        # Unselected raw discovery excerpts are retained in the audit resource,
        # while model input contains only the exact selected evidence.
        self.assertNotIn('discoveries', json.loads(prompt.split('\nDATA\n')[1])['input']['corpus_evidence'])
        self.assertEqual(self.store.read_context('session'), self.root)

    def test_rejection_uncertainty_atomic_failure_and_abandonment_leave_no_proposal(self):
        self.prepare()
        for verdict in ('REJECT','UNCERTAIN'):
            self.reviewer.value = self.reviewer.value.model_copy(update={'verdict': verdict})
            self.assertEqual(self.generate(verdict).kind, 'FAILURE')
        self.reviewer.value = Reviewer().value
        original = self.store._put
        def fail(entity, *args, **kwargs):
            if entity.id.endswith(':retrieval-trace'):
                raise RuntimeError('Injected trace persistence failure')
            return original(entity,*args,**kwargs)
        with patch.object(self.store,'_put',side_effect=fail):
            self.assertEqual(self.generate('rollback').kind,'FAILURE')
        self.reviewer.callback = lambda: self.service.abandon_request('session','admin','abandoned')
        self.assertEqual(self.generate('abandoned').kind,'FAILURE')
        self.assertFalse(self.store.owned('session','ChangeProposal'))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM entities WHERE namespace<>'active'").fetchone()[0],0)

    def test_scope_revocation_and_concurrent_change_block_final_storage(self):
        def revoke(*args,**kwargs):
            self.service.policy = self.service.policy.model_copy(update={'scopes': {}})
            return response()
        self.client.fetch_preparation_documents.side_effect = revoke
        self.assertEqual(self.prepare().kind,'FAILURE')
        self.models.assert_not_called()

    def test_uncited_selected_assessment_context_remains_available_to_the_evaluator(self):
        doc = copy.deepcopy(response()['documents'][0])
        doc.update(id='assessment-context', text='Synthetic context: review the explanation of prompting choices explicitly.')
        doc['metadata'].update(source='wp3:context', resource_key=resource_key('wp3:context','v1'), title='Synthetic assessment context')
        combined = {'documents': [*response()['documents'],doc], 'truncated': False}
        self.client.search.return_value = combined
        self.client.fetch_preparation_documents.return_value = combined
        value = plan(combined['documents']).model_copy(update={'min_resources': 2})
        self.assertIsInstance(self.prepare(value=value), PreparedSources)
        result = self.generate()
        proposal = self.store.read(result.proposal_refs[0],owner='session')
        saved = proposal_candidates(self.store,proposal)
        self.assertTrue(any(e.id=='wp3:context' for e in saved))
        syllabus = next(e for e in saved if e.id.endswith(':syllabus'))
        self.service.decide('session','admin',proposal.ref,'APPROVE','Review exact selected source input')
        self.service.apply('session','admin',proposal.ref,'syllabus')
        project = self.service.initialize_authoring_project('session','admin',{
            'project_id':'selected-project','base_context':self.store.read_context('session').ref,
            'syllabus':syllabus.ref},request_id='project')
        self.service.decide('session','admin',project.proposal,'APPROVE','Review exact project input')
        self.service.apply('session','admin',project.proposal,'project')
        from tests.generator_fixtures import SyntheticModels
        from aimpro.didactic import CorpusCitation
        models = SyntheticModels()
        def cite_context(data,draft):
            item = draft.units[0].items[0]
            citation = CorpusCitation(resource_id='wp3:context',resource_version='v1',
                document_ids=('assessment-context',),supported_claim=doc['text'])
            item = item.model_copy(update={'citations': (*item.citations,citation)})
            return draft.model_copy(update={'units': (draft.units[0].model_copy(update={'items': (item,)}),)})
        models.transform = cite_context
        response_value = self.service.generate_project_assessments('session','admin',{
            'project':project.project,'base_context':self.store.read_context('session').ref},
            request_id='evaluator',authoring_factory=models.factory)
        self.assertEqual(response_value.kind,'PROPOSAL')

    def test_source_export_change_during_models_prevents_a_proposal(self):
        project_file = Path(self.temp.name)/'source.json'
        project_file.write_bytes(DEFAULT_PROJECT.read_bytes())
        self.service.prepare_aimpro_syllabus_sources('session','admin',project_file,plan(),
            request_id='sources',search_client_factory=self.client_factory)
        self.reviewer.callback = lambda: project_file.write_bytes(project_file.read_bytes()+b'\n')
        result = self.service.generate_aimpro_syllabus('session','admin',project_file,request_id='selected',
            source_scope='wp3',prepared_sources='sources',authoring_factory=self.models)
        self.assertEqual(result.kind,'FAILURE')
        self.assertFalse(self.store.owned('session','ChangeProposal'))

    def test_concurrent_context_edit_during_models_is_not_silently_rebased(self):
        self.prepare()
        def change():
            candidate = self.root.model_copy(update={'version':'concurrent'})
            proposal = self.service.propose('session','admin',(self.root.ref,),(candidate,),'Synthetic concurrent edit')
            self.service.decide('session','admin',proposal.ref,'APPROVE','Synthetic review')
            self.service.apply('session','admin',proposal.ref,'concurrent')
        self.reviewer.callback = change
        self.assertEqual(self.generate().kind,'FAILURE')
        self.assertEqual(len(self.store.owned('session','ChangeProposal')),1)

    def test_atomic_terminal_result_failure_does_not_leave_accepted_candidates(self):
        self.prepare()
        original = self.store.finish_request
        calls = 0
        def fail_once(*args,**kwargs):
            nonlocal calls
            calls += 1
            if calls==1:
                raise RuntimeError('Injected result persistence failure')
            return original(*args,**kwargs)
        with patch.object(self.store,'finish_request',side_effect=fail_once):
            self.assertEqual(self.generate().kind,'FAILURE')
        self.assertFalse(self.store.owned('session','ChangeProposal'))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM entities WHERE namespace<>'active'").fetchone()[0],0)

    def test_prepared_packet_rejects_mismatched_model_evidence(self):
        prepared = self.prepare()
        broken = prepared.model_copy(update={'data':prepared.data.model_copy(update={'corpus_evidence':None})})
        with self.assertRaises(ValueError):
            PreparedSources.model_validate(broken.model_dump(mode='json'))

    def test_cli_prepares_without_models_and_generates_without_retrieval(self):
        policy_file = Path(self.temp.name)/'policy.json'
        policy_file.write_text(self.service.policy.model_dump_json())
        plan_file = Path(self.temp.name)/'plan.json'
        plan_file.write_text(plan().model_dump_json())
        args=['--db',str(self.path),'--policy',str(policy_file),'--context','session','--subject','admin']
        with patch('learning.__main__._aimpro_search_client',self.client_factory), \
             patch('learning.__main__._aimpro_authoring',side_effect=AssertionError('Preparation must not create models')), redirect_stdout(StringIO()) as output:
            self.assertEqual(main([*args,'prepare-aimpro-syllabus-sources',str(DEFAULT_PROJECT),
                '--plan',str(plan_file),'--request-id','sources']),0)
        self.assertEqual(json.loads(output.getvalue())['kind'],'SOURCE_PREPARATION')
        with patch('learning.__main__._aimpro_search',side_effect=AssertionError('No new retrieval')), \
             patch('learning.__main__._aimpro_authoring',self.models), redirect_stdout(StringIO()) as output:
            self.assertEqual(main([*args,'generate-aimpro-syllabus',str(DEFAULT_PROJECT),'--source-scope','wp3',
                '--prepared-sources','sources','--request-id','selected']),0)
        self.assertEqual(json.loads(output.getvalue())['kind'],'PROPOSAL')

    def test_invalid_source_action_anchor_is_rejected_before_client_or_reservation(self):
        from tests.test_syllabus_coverage import requirements
        action = requirements(source())[0].model_copy(update={'source_quote': 'Invented source text'})
        value = plan().model_copy(update={'coverage_requirements': (action,)})
        with self.assertRaisesRegex(ValueError, 'quote does not match'):
            self.prepare(value=value)
        self.client_factory.assert_not_called()
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE id='sources'").fetchone())

    def test_required_actions_are_reserved_persisted_reviewed_and_resolved(self):
        from tests.test_syllabus_coverage import covered_syllabus, requirements
        value = plan().model_copy(update={'coverage_requirements': requirements(source())})
        prepared = self.prepare(value=value)
        self.assertIsInstance(prepared, PreparedSources)
        self.assertEqual(prepared.data.corpus_evidence.selection.coverage_requirements, value.coverage_requirements)
        self.assertEqual(self.generate('missing').kind, 'FAILURE')
        self.assertEqual(self.reviewer.calls, [])
        self.curator.value = covered_syllabus(prepared.data)
        result = self.generate('covered')
        self.assertEqual(result.kind, 'PROPOSAL')
        proposal = self.store.read(result.proposal_refs[0], owner='session')
        saved = proposal_candidates(self.store, proposal)
        design = next(e for e in saved if e.type == 'LearningDesign')
        self.service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Explicit synthetic review of source-action coverage')
        self.service.apply('session', 'admin', proposal.ref, 'covered')
        approved = self.service.approved_aimpro_syllabus('session', 'admin', design.ref)
        self.assertEqual(approved.source.corpus_evidence.selection.coverage_requirements, value.coverage_requirements)
        self.assertEqual(approved.artifact.draft.units[0].coverage, self.curator.value.units[0].coverage)
        row = self.store.db.execute("SELECT payload FROM requests WHERE id='covered'").fetchone()
        self.assertTrue(json.loads(row['payload'])['model_input']['corpus_evidence']['selection']['coverage_requirements'])


class ExactPreparationFetchTest(unittest.TestCase):
    def test_postgres_exact_fetch_pins_scope_version_content_and_complete_selection(self):
        doc=response()['documents'][0]
        ref=PreparationDocumentRef.model_validate(plan().documents[0].model_dump(include=set(PreparationDocumentRef.model_fields)))
        backend=PostgresBackend('not-a-real-dsn',unlimited_text=True)
        connection=MagicMock()
        connection.__enter__.return_value.execute.return_value.fetchall.return_value=[doc]
        with patch('psycopg.connect',return_value=connection) as connect:
            result=backend.fetch_preparation_documents([ref],scope=SearchScope(mode='PREPARATION',source_scope_keys=('wp3',)))
            self.assertEqual(result['documents'][0]['id'],doc['id'])
            self.assertIn('default_transaction_read_only=on',connect.call_args.kwargs['options'])
            query,parameters=connection.__enter__.return_value.execute.call_args.args
            self.assertIn('id = ANY(%s)',query)
            self.assertEqual(parameters,(['wp3'],['chunk-1']))
            for changed in ({'content_sha256':'0'*64},{'resource_version':'v2'}):
                with self.assertRaises(SearchError):
                    backend.fetch_preparation_documents([ref.model_copy(update=changed)],scope=SearchScope(mode='PREPARATION',source_scope_keys=('wp3',)))
            connection.__enter__.return_value.execute.return_value.fetchall.return_value=[]
            with self.assertRaises(SearchError):
                backend.fetch_preparation_documents([ref],scope=SearchScope(mode='PREPARATION',source_scope_keys=('wp3',)))
        with patch('psycopg.connect',side_effect=AssertionError('Reject before connection')):
            for scope in (SearchScope(mode='LEARNING',resource_keys=(resource_key('wp3:test','v1'),)), SearchScope(mode='PREPARATION')):
                with self.assertRaises(ValueError):
                    backend.fetch_preparation_documents([ref],scope=scope)
