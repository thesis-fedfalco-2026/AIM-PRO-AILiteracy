from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from aimpro.audit import DEFAULT_PROJECT
from aimpro.lead import prepare_input
from aimpro.syllabus import checked_syllabus, generate
from aimpro.syllabus_state import SyllabusArtifact
from learning.contracts import EntityRef, make_entity
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.policies import ScopeGrant
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from learning.validation import check_readiness
from tests.syllabus_fixtures import Curator, Reviewer, source, syllabus
from tests.test_aimpro_retrieval import response as search_response
from tests.test_learning_context import policy


class SyllabusContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = source()
        cls.draft = syllabus(cls.data)

    def test_curator_generates_and_a_separate_lead_only_reviews(self):
        curator, reviewer = Curator(self.draft), Reviewer()
        draft, verdict = generate(self.data, dispatcher=curator, lead=reviewer)
        self.assertEqual(draft, self.draft)
        self.assertEqual(verdict.verdict, 'ACCEPT')
        self.assertEqual(len(curator.calls), 1)
        self.assertEqual(curator.calls[0][0], 'syllabus-designer')
        self.assertEqual(len(reviewer.calls), 1)
        self.assertIn('never a replacement syllabus', reviewer.calls[0][0])
        payload = json.loads(curator.calls[0][1].split('\nDATA\n')[1])
        self.assertIn('use fictional customer details only.', curator.calls[0][1])
        self.assertEqual(set(payload['allowed_practice_ids_by_target']), {self.draft.units[0].source_target_id})

    def test_fingerprints_and_coverage_are_exact(self):
        unit = self.draft.units[0]
        for changed in (
            self.draft.model_copy(update={'source_sha256': 'wrong'}),
            self.draft.model_copy(update={'metamodel_fingerprint': 'wrong'}),
            self.draft.model_copy(update={'units': (unit.model_copy(update={'source_target_id': 'invented'}),)}),
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                checked_syllabus(self.data, changed)

    def test_unknown_or_duplicate_competencies_practices_and_intents_are_rejected(self):
        unit = self.draft.units[0]
        for fields in (
            {'source_competency_ids': ('invented',)},
            {'source_competency_ids': unit.source_competency_ids * 2},
            {'source_practice_ids': ('invented',)},
            {'source_practice_ids': unit.source_practice_ids * 2},
            {'planned_intents': ('PRACTICE', 'PRACTICE')},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                checked_syllabus(self.data, self.draft.model_copy(update={'units': (unit.model_copy(update=fields),)}))

    def test_resource_versions_and_excerpt_ids_are_checked_before_lead_review(self):
        unit = self.draft.units[0]
        for fields in ({'resource_id': 'invented'}, {'resource_version': 'wrong'},
                       {'document_ids': ('invented',)}, {'document_ids': ('chunk-1', 'chunk-1')}):
            citation = unit.corpus_citations[0].model_copy(update=fields)
            curator = Curator(self.draft.model_copy(update={
                'units': (unit.model_copy(update={'corpus_citations': (citation,)}),)}))
            reviewer = Reviewer()
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                generate(self.data, dispatcher=curator, lead=reviewer)
            self.assertEqual(reviewer.calls, [])

    def test_multiple_distinct_units_can_cover_one_target_but_keys_are_unique(self):
        unit = self.draft.units[0]
        second = unit.model_copy(update={'key': 'practice', 'title': 'Practice', 'purpose': 'Write and explain a fictional prompt.'})
        checked_syllabus(self.data, self.draft.model_copy(update={'units': (unit, second)}))
        with self.assertRaisesRegex(ValueError, 'unique'):
            checked_syllabus(self.data, self.draft.model_copy(update={'units': (unit, unit)}))

    def test_grounding_and_semantic_support_are_mandatory(self):
        curator, reviewer = Curator(self.draft), Reviewer()
        with self.assertRaisesRegex(ValueError, 'corpus evidence'):
            generate(prepare_input(), dispatcher=curator, lead=reviewer)
        self.assertEqual(curator.calls, [])
        for fields in ({'verdict': 'REJECT'}, {'verdict': 'UNCERTAIN'},
                       {'citation_support': False}, {'source_alignment': False}):
            reviewer.value = Reviewer().value.model_copy(update=fields)
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, 'semantic review'):
                generate(self.data, dispatcher=curator, lead=reviewer)

    def test_review_budget_and_wrong_output_stop_generation(self):
        curator, reviewer = Curator(self.draft), Reviewer()
        with self.assertRaisesRegex(ValueError, 'budget'):
            generate(self.data, dispatcher=curator, lead=reviewer, max_context_chars=10)
        self.assertEqual(reviewer.calls, [])
        reviewer.value = self.draft
        with self.assertRaisesRegex(ValueError, 'structured syllabus review'):
            generate(self.data, dispatcher=curator, lead=reviewer)


class SyllabusServiceTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = Path(self.temp.name) / 'state.sqlite'
        self.store = LearningStore(self.db_path)
        self.addCleanup(self.store.close)
        trusted = policy().model_copy(update={'scopes': {
            'wp3': ScopeGrant(contexts=['session'], subjects=['admin'], sources=['wp3'])}})
        self.service = LearningService(self.store, load_contract(), trusted,
            Mock(side_effect=AssertionError('Learning workers must not run')))
        self.root = self.service.bootstrap('session', 'admin')
        self.curator, self.reviewer = Curator(), Reviewer()
        self.factory = Mock(return_value=(self.curator, self.reviewer, None))
        self.search = Mock(return_value=search_response())
        self.search_factory = Mock(return_value=self.search)

    def generate(self, request_id='syllabus', **kwargs):
        values = dict(request_id=request_id, authoring_factory=self.factory,
                      source_scope='wp3', query='prompting', k=3, search_factory=self.search_factory)
        values.update(kwargs)
        return self.service.generate_aimpro_syllabus('session', 'admin', DEFAULT_PROJECT, **values)

    def pending(self, request_id='syllabus'):
        response = self.generate(request_id)
        self.assertEqual(response.kind, 'PROPOSAL')
        proposal = self.store.read(response.proposal_refs[0], owner='session')
        saved = proposal_candidates(self.store, proposal)
        design = next(e for e in saved if e.type == 'LearningDesign')
        return response, proposal, saved, design

    def approve_apply(self, proposal, operation='import'):
        self.service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Reviewed synthetic syllabus in this test')
        self.service.apply('session', 'admin', proposal.ref, operation)

    def test_pending_review_application_and_approved_resolution_are_distinct(self):
        response, proposal, saved, design = self.pending()
        self.assertEqual(self.store.read_context('session'), self.root)
        self.assertEqual(proposal.fields['status'], 'AWAITING_DECISION')
        with self.assertRaises(ValueError):
            self.service.approved_aimpro_syllabus('session', 'admin', design.ref)
        self.service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Reviewed synthetic syllabus')
        with self.assertRaises(ValueError):
            self.service.approved_aimpro_syllabus('session', 'admin', design.ref)
        self.service.apply('session', 'admin', proposal.ref, 'import')
        approved = self.service.approved_aimpro_syllabus('session', 'admin', design.ref)
        self.assertEqual(approved.artifact.draft, self.curator.value)
        self.assertEqual(approved.artifact.outline, design.ref)
        self.assertEqual(approved.proposal.id, proposal.id)
        self.assertIn('chunk-1', approved.source.model_dump_json())
        self.assertEqual(approved.source.findings, source().findings)
        self.assertIn('contract_findings', proposal.fields['proposedChange'])
        self.assertEqual(self.generate(), response)
        self.assertEqual(self.search.call_count, 1)
        self.assertEqual(self.factory.call_count, 1)
        root = self.store.read_context('session')
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        for field in ('resourceBindings', 'learningStates', 'activityOccurrences'):
            self.assertEqual(root.fields[field], [])
        self.assertFalse(any(e.type in {'ActivityDefinition', 'Rubric', 'AssessmentSpecification',
            'ResourceBinding', 'Evaluation', 'LearningState', 'RuleDefinition'} for e in saved))

    def test_applied_empty_outline_cannot_activate(self):
        _, proposal, saved, design = self.pending()
        self.approve_apply(proposal)
        context = self.service._context('session', 'admin')
        findings = check_readiness(context.snapshot, design.ref, 'advance')
        self.assertTrue(any(f.code == 'R06' and 'Draft node' in f.reason for f in findings))
        root = context.snapshot.context
        active = root.model_copy(update={'version': 'activate', 'fields': {**root.fields, 'mode': 'LEARNING', 'status': 'ACTIVE'}})
        with self.assertRaises(ValueError):
            self.service.propose('session', 'admin', (root.ref,), (active,), 'Attempt premature activation')

    def test_source_constraints_and_corpus_version_are_preserved_without_binding(self):
        _, _, saved, design = self.pending()
        strategy = next(e for e in saved if e.type == 'Strategy')
        self.assertIn('use fictional customer details only.', strategy.fields['constraints'])
        corpus = next(e for e in saved if e.id == 'wp3:test')
        self.assertEqual(corpus.version, 'v1')
        self.assertEqual(corpus.fields['contentOrLocator'], 'https://example.org/guide')
        payload = next(e for e in saved if e.type == 'Resource' and e.id.endswith(':syllabus'))
        artifact = SyllabusArtifact.model_validate_json(payload.fields['contentOrLocator'])
        self.assertEqual(artifact.outline, design.ref)
        self.assertIn(corpus.ref.model_dump(), payload.fields['derivedFrom'])
        self.assertEqual(self.search.call_args.kwargs['scope'].source_scope_keys, ('wp3',))

    def test_authorization_is_checked_before_source_retrieval_or_agents(self):
        for subject, scope in (('learner', 'wp3'), ('admin', 'forbidden')):
            with patch('aimpro.syllabus_service.prepare_input') as prepare, self.assertRaises(ValueError):
                self.service.generate_aimpro_syllabus('session', subject, DEFAULT_PROJECT,
                    request_id='denied', authoring_factory=self.factory,
                    source_scope=scope, query='prompting', search_factory=self.search_factory)
            prepare.assert_not_called()
        self.search_factory.assert_not_called()
        self.factory.assert_not_called()

    def test_empty_truncated_and_out_of_scope_retrieval_never_reach_agents(self):
        for i, result in enumerate(({'documents': [], 'truncated': False},
                {**search_response(), 'truncated': True},
                {'documents': [{**search_response()['documents'][0], 'metadata': {
                    **search_response()['documents'][0]['metadata'], 'source_scope': 'other'}}]})):
            self.search.return_value = result
            self.assertEqual(self.generate(str(i)).kind, 'FAILURE')
        self.factory.assert_not_called()
        self.assertEqual(self.store.owned('session', 'ChangeProposal'), ())

    def test_rejected_unsupported_or_invalid_draft_leaves_no_partial_candidates(self):
        self.reviewer.value = self.reviewer.value.model_copy(update={'citation_support': False})
        self.assertEqual(self.generate().kind, 'FAILURE')
        self.assertEqual(self.generate().kind, 'FAILURE')
        self.assertEqual(self.factory.call_count, 1)
        self.assertEqual(self.store.owned('session', 'ChangeProposal'), ())
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM entities WHERE namespace <> 'active'").fetchone()[0], 0)

    def test_request_payload_changes_and_pending_requests_conflict(self):
        self.generate()
        for values in ({'query': 'different'}, {'k': 1}):
            with self.subTest(values=values), self.assertRaises(StateConflict):
                self.generate(**values)
        self.assertEqual(self.search.call_count, 1)
        self.store.claim_request('pending', 'session', 'other payload')
        with self.assertRaises(StateConflict):
            self.generate('pending')

    def test_changed_source_cannot_reuse_request_identity(self):
        self.generate()
        project = json.loads(DEFAULT_PROJECT.read_text())
        project['metadata']['project']['name'] = 'Changed source'
        path = Path(self.temp.name) / 'changed.json'
        path.write_text(json.dumps(project))
        with self.assertRaises(StateConflict):
            self.service.generate_aimpro_syllabus('session', 'admin', path,
                request_id='syllabus', authoring_factory=self.factory, source_scope='wp3',
                query='prompting', k=3, search_factory=self.search_factory)

    def test_final_write_failure_rolls_back_proposal_and_candidates(self):
        original = self.store.finish_request
        calls = 0
        def fail_first(*args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError('Injected final write failure')
            return original(*args)
        with patch.object(self.store, 'finish_request', side_effect=fail_first):
            self.assertEqual(self.generate().kind, 'FAILURE')
        self.assertEqual(self.store.owned('session', 'ChangeProposal'), ())
        self.assertEqual(self.store.read_context('session'), self.root)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM entities WHERE namespace <> 'active'").fetchone()[0], 0)

    def test_abandonment_and_concurrent_changes_prevent_stale_storage(self):
        self.reviewer.callback = lambda: self.service.abandon_request('session', 'admin', 'syllabus')
        self.assertEqual(self.generate().kind, 'FAILURE')
        self.assertEqual(self.store.owned('session', 'ChangeProposal'), ())
        def change():
            proposal = self.service.propose('session', 'admin', (self.root.ref,),
                (make_entity('Topic', 'concurrent', {'name': 'Concurrent', 'definition': 'Concurrent edit'}),), 'Concurrent edit')
            self.approve_apply(proposal, 'concurrent')
        self.reviewer.callback = change
        self.assertEqual(self.generate('stale').kind, 'FAILURE')
        self.assertEqual(len(self.store.owned('session', 'ChangeProposal')), 1)

    def test_resolver_is_read_only_and_rejects_foreign_or_superseded_design(self):
        _, proposal, _, design = self.pending()
        self.approve_apply(proposal)
        before = self.store.db.total_changes
        first = self.service.approved_aimpro_syllabus('session', 'admin', design.ref)
        self.assertEqual(self.service.approved_aimpro_syllabus('session', 'admin', design.ref), first)
        self.assertEqual(self.store.db.total_changes, before)
        with self.assertRaises(ValueError):
            self.service.approved_aimpro_syllabus('session', 'learner', design.ref)
        _, second, _, next_design = self.pending('next')
        self.approve_apply(second, 'next')
        with self.assertRaises(ValueError):
            self.service.approved_aimpro_syllabus('session', 'admin', design.ref)
        self.assertEqual(self.service.approved_aimpro_syllabus('session', 'admin', next_design.ref).proposal.id, second.id)
        foreign_policy = self.service.policy.model_dump()
        foreign_policy['subjects']['admin']['actions']['other'] = foreign_policy['subjects']['admin']['actions']['session']
        self.service.policy = type(self.service.policy).model_validate(foreign_policy)
        self.service.bootstrap('other', 'admin')
        with self.assertRaises(ValueError):
            self.service.approved_aimpro_syllabus('other', 'admin', next_design.ref)

    def test_resolver_rechecks_current_human_authority_and_latest_decision(self):
        _, proposal, _, design = self.pending()
        self.approve_apply(proposal)
        original = self.service.policy
        grant = original.subjects['admin']
        self.service.policy = original.model_copy(update={'subjects': {**original.subjects,
            'admin': grant.model_copy(update={'actions': {'session': ['read', 'propose']}})}})
        with self.assertRaisesRegex(ValueError, 'approval'):
            self.service.approved_aimpro_syllabus('session', 'admin', design.ref)
        self.service.policy = original
        self.service.decide('session', 'admin', proposal.ref, 'REJECT', 'Revoke synthetic test decision')
        with self.assertRaises(ValueError):
            self.service.approved_aimpro_syllabus('session', 'admin', design.ref)

    def test_cli_uses_authoring_and_resolution_without_learning_workers(self):
        from learning.__main__ import main
        policy_path = Path(self.temp.name) / 'policy.json'
        policy_path.write_text(self.service.policy.model_dump_json())
        args = ['--db', str(self.db_path), '--policy', str(policy_path), '--subject', 'admin', '--context', 'session']
        output = StringIO()
        with patch('learning.__main__._aimpro_authoring', self.factory), \
             patch('learning.__main__._aimpro_search', self.search_factory), redirect_stdout(output):
            code = main([*args, 'generate-aimpro-syllabus', str(DEFAULT_PROJECT), '--request-id', 'cli',
                         '--source-scope', 'wp3', '--query', 'prompting', '--k', '3'])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        proposal = self.store.read(EntityRef.model_validate(result['proposal_refs'][0]), owner='session')
        design = next(e for e in proposal_candidates(self.store, proposal) if e.type == 'LearningDesign')
        self.approve_apply(proposal)
        output = StringIO()
        with patch('learning.__main__._aimpro_authoring', side_effect=AssertionError('No model')), redirect_stdout(output):
            code = main([*args, 'show-aimpro-syllabus', design.ref.model_dump_json()])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['artifact']['outline'], design.ref.model_dump())
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            main([*args, 'generate-aimpro-syllabus', str(DEFAULT_PROJECT), '--request-id', 'missing-source'])


if __name__ == '__main__':
    unittest.main()
