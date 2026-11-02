from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from aimpro.audit import DEFAULT_PROJECT
from learning.contracts import make_entity
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from learning.validation import check_readiness
from tests.aimpro_fixtures import TeachingLead
from tests.test_learning_context import policy


class AimproExecutionTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LearningStore(Path(self.temp.name) / 'state.sqlite')
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), policy(), Mock(side_effect=AssertionError('ALM workers must not run')))
        self.root = self.service.bootstrap('session', 'admin')
        self.lead = TeachingLead()
        self.factory = Mock(return_value=(self.lead, None))

    def generate(self, request_id='generate', subject='admin'):
        return self.service.generate_aimpro('session', subject, DEFAULT_PROJECT,
            request_id=request_id, lead_factory=self.factory)

    def test_generation_stores_pending_candidates_then_approval_and_apply_are_distinct(self):
        response = self.generate()
        self.assertEqual(response.kind, 'PROPOSAL')
        proposal = self.store.read(response.proposal_refs[0], owner='session')
        self.assertEqual(proposal.fields['status'], 'AWAITING_DECISION')
        self.assertEqual(self.store.read_context('session'), self.root)
        saved = proposal_candidates(self.store, proposal)
        design = next(e for e in saved if e.type == 'LearningDesign')
        with self.assertRaises(ValueError):
            self.store.read(design.ref, owner='session')
        self.service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Reviewed synthetic teaching draft')
        self.assertEqual(self.store.read_context('session'), self.root)
        self.service.apply('session', 'admin', proposal.ref, 'import')
        root = self.store.read_context('session')
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        self.assertEqual(root.fields['learningDesign'], design.ref.model_dump())
        self.assertEqual(root.fields['learningStates'], [])
        self.assertEqual(root.fields['activityOccurrences'], [])
        self.assertEqual(self.store.owned('session', 'LearningEvidence'), ())
        self.assertEqual(self.store.owned('session', 'HumanDecision')[0].fields['decision'], 'APPROVE')
        self.assertEqual(self.generate(), response)
        self.assertEqual(self.factory.call_count, 1)

    def test_provenance_constraints_and_gaps_are_preserved(self):
        response = self.generate()
        proposal = self.store.read(response.proposal_refs[0], owner='session')
        saved = proposal_candidates(self.store, proposal)
        self.assertIn('contract_findings', proposal.fields['proposedChange'])
        self.assertTrue(any(e.type == 'Resource' and 'source snapshot' in e.fields['title'] for e in saved))
        for item in saved:
            self.assertEqual(item.provenance.origin, 'GENERATED_PROPOSAL')
            self.assertIn('source_sha256', item.provenance.sources[0])
            if item.type == 'ActivityDefinition':
                self.assertIn('use fictional customer details only.', item.fields['instruction'])
                self.assertTrue(item.fields['resourceRequirements'])
        self.assertFalse(any(e.type in {'ResourceBinding', 'LearningState', 'Evaluation', 'RuleDefinition'} for e in saved))

    def test_imported_design_cannot_activate_with_unresolved_resources_and_rules(self):
        response = self.generate()
        proposal = response.proposal_refs[0]
        self.service.decide('session', 'admin', proposal, 'APPROVE', 'Reviewed')
        self.service.apply('session', 'admin', proposal, 'import')
        context = self.service._context('session', 'admin')
        findings = check_readiness(context.snapshot, context.snapshot.context.fields['learningDesign'], 'advance',
            learner_ref=context.participant.ref, policy=context.policy, subject_key='admin')
        self.assertTrue(any(f.code == 'R08' for f in findings))
        root = context.snapshot.context
        active = root.model_copy(update={'version': 'activate', 'fields': {**root.fields, 'mode': 'LEARNING', 'status': 'ACTIVE'}})
        with self.assertRaises(ValueError):
            self.service.propose('session', 'admin', (root.ref,), (active,), 'Activate unfinished design')

    def test_replay_does_not_generate_twice_and_unapproved_apply_is_denied(self):
        first = self.generate()
        self.assertEqual(self.generate(), first)
        self.assertEqual(len(self.lead.calls), 2)
        with self.assertRaises(ValueError):
            self.service.apply('session', 'admin', first.proposal_refs[0], 'unapproved')
        self.assertEqual(self.store.read_context('session'), self.root)

    def test_unauthorized_subject_stops_before_model(self):
        with self.assertRaises(ValueError):
            self.generate(subject='learner')
        self.factory.assert_not_called()

    def test_rejected_draft_leaves_no_candidates(self):
        self.lead.verdict = 'REJECT'
        self.assertEqual(self.generate().kind, 'FAILURE')
        self.assertEqual(self.store.owned('session', 'ChangeProposal'), ())
        self.assertEqual(self.store.read_context('session'), self.root)

    def test_final_write_failure_rolls_back_proposal(self):
        original = self.store.finish_request
        count = 0
        def fail_first(*args):
            nonlocal count
            count += 1
            if count == 1:
                raise RuntimeError('injected failure')
            return original(*args)
        with patch.object(self.store, 'finish_request', side_effect=fail_first):
            self.assertEqual(self.generate().kind, 'FAILURE')
        self.assertEqual(self.store.owned('session', 'ChangeProposal'), ())
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM entities WHERE namespace <> 'active'").fetchone()[0], 0)

    def test_abandonment_during_generation_prevents_proposal_storage(self):
        self.lead.callback = lambda: self.service.abandon_request('session', 'admin', 'generate')
        response = self.generate()
        self.assertEqual(response.kind, 'FAILURE')
        self.assertEqual(self.store.owned('session', 'ChangeProposal'), ())
        self.assertEqual(self.generate(), response)

    def test_changed_source_cannot_reuse_request_identity(self):
        self.generate()
        project = json.loads(DEFAULT_PROJECT.read_bytes())
        project['metadata']['project']['name'] = 'Changed project'
        path = Path(self.temp.name) / 'changed.json'
        path.write_text(json.dumps(project), encoding='utf-8')
        with self.assertRaises(StateConflict):
            self.service.generate_aimpro('session', 'admin', path, request_id='generate', lead_factory=self.factory)
        self.assertEqual(len(self.lead.calls), 2)

    def test_context_change_during_generation_prevents_stale_candidate_save(self):
        def change_context():
            proposal = self.service.propose('session', 'admin', (self.root.ref,),
                (make_entity('Topic', 'concurrent-topic', {'name': 'Concurrent', 'definition': 'External edit'}),), 'Concurrent edit')
            self.service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Reviewed')
            self.service.apply('session', 'admin', proposal.ref, 'concurrent')
        self.lead.callback = change_context
        self.assertEqual(self.generate().kind, 'FAILURE')
        self.assertEqual(len({p.id for p in self.store.owned('session', 'ChangeProposal')}), 1)

    def test_cli_generates_a_pending_proposal_using_the_existing_store(self):
        from learning.__main__ import main
        policy_path = Path(self.temp.name) / 'policy.json'
        policy_path.write_text(self.service.policy.model_dump_json(), encoding='utf-8')
        output = StringIO()
        with patch('learning.__main__._aimpro_lead', self.factory), redirect_stdout(output):
            code = main(['--db', str(Path(self.temp.name) / 'state.sqlite'), '--policy', str(policy_path),
                '--subject', 'admin', '--context', 'session', 'generate-aimpro', str(DEFAULT_PROJECT), '--request-id', 'cli'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['kind'], 'PROPOSAL')
        self.assertEqual(self.store.read_context('session'), self.root)
