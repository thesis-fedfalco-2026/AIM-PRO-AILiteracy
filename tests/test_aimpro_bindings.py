import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aimpro.audit import DEFAULT_PROJECT
from learning.decisions import approval_valid, proposal_candidates
from learning.metamodel import load_contract
from learning.policies import ScopeGrant
from learning.service import LearningService
from learning.store import LearningStore
from tests.aimpro_fixtures import TeachingLead
from tests.test_aimpro_retrieval import grounded, response
from tests.test_learning_context import policy


class AimproBindingTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.sqlite'
        self.store = LearningStore(self.path); self.addCleanup(self.store.close)
        rules = policy().model_copy(update={'scopes': {
            'wp3': ScopeGrant(contexts=['session'], subjects=['admin'], sources=['wp3'])}})
        self.service = LearningService(self.store, load_contract(), rules, lambda: None)
        self.root = self.service.bootstrap('session', 'admin')
        _, value = grounded()
        result = self.service.generate_aimpro('session', 'admin', DEFAULT_PROJECT, request_id='teaching',
            lead_factory=lambda: (TeachingLead(value=value), None), source_scope='wp3', query='prompting',
            search_factory=lambda: lambda *a, **kw: response())
        self.source = result.proposal_refs[0]
        self.saved = proposal_candidates(self.store, self.store.read(self.source, owner='session'))
        self.activity = next(e for e in self.saved if e.type == 'ActivityDefinition')
        self.resource = next(e for e in self.saved if e.id == 'wp3:test')
        self.selection = {'activity': self.activity.ref.model_dump(),
            'requirement': self.activity.fields['resourceRequirements'][0],
            'resource': self.resource.ref.model_dump(), 'usage_scope': 'wp3'}

    def propose(self, selections=None):
        return self.service.propose_aimpro_bindings('session', 'admin', self.source,
            [self.selection] if selections is None else selections)

    def test_new_payload_needs_its_own_approval_then_preserves_draft_state(self):
        proposal = self.propose()
        self.assertEqual(proposal.fields['status'], 'AWAITING_DECISION')
        self.assertEqual(self.store.read_context('session'), self.root)
        self.assertEqual(self.store.read(self.source, owner='session').fields['status'], 'AWAITING_DECISION')
        saved = proposal_candidates(self.store, proposal)
        binding = next(e for e in saved if e.type == 'ResourceBinding')
        self.assertIsNone(binding.fields.get('approvalDecision'))
        self.assertNotEqual(binding.fields['reviewPayloadKey'], 'pending')
        self.assertEqual(binding.fields['resource'], self.resource.ref.model_dump())
        with self.assertRaises(ValueError):
            self.service.apply('session', 'admin', proposal.ref, 'unapproved')
        self.service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Reviewed synthetic design and resource selection')
        self.service.apply('session', 'admin', proposal.ref, 'import-with-binding')
        context = self.service._context('session', 'admin')
        applied = context.snapshot.get(binding.ref)
        self.assertTrue(approval_valid(applied, context.snapshot, self.service.policy))
        self.assertEqual(context.snapshot.context.fields['mode'], 'PREPARATION')
        self.assertEqual(context.snapshot.context.fields['status'], 'DRAFT')
        self.assertEqual(context.snapshot.context.fields['learningStates'], [])
        self.assertEqual(self.store.owned('session', 'LearningEvidence'), ())

    def test_empty_duplicate_and_wrong_requirement_selections_are_rejected(self):
        wrong = {**self.selection, 'requirement': self.resource.ref.model_dump()}
        for selections in ([], [self.selection, self.selection], [wrong]):
            with self.assertRaises(ValueError):
                self.propose(selections)
        self.assertEqual(len(self.store.owned('session', 'ChangeProposal')), 1)

    def test_generated_material_is_not_silently_treated_as_a_corpus_source(self):
        generated = next(e for e in self.saved if e.type == 'Resource' and e.id != self.resource.id)
        with self.assertRaises(ValueError):
            self.propose([{**self.selection, 'resource': generated.ref.model_dump()}])

    def test_scope_and_subject_authority_are_checked(self):
        with self.assertRaises(ValueError):
            self.service.propose_aimpro_bindings('session', 'learner', self.source, [self.selection])
        self.service.policy = self.service.policy.model_copy(update={'scopes': {}})
        with self.assertRaises(ValueError):
            self.propose()

    def test_prior_human_decision_is_not_reused(self):
        self.service.decide('session', 'admin', self.source, 'APPROVE', 'Original design only')
        with self.assertRaises(ValueError):
            self.propose()

    def test_cli_prepares_another_pending_proposal_without_applying(self):
        from learning.__main__ import main
        policy_path = Path(self.temp.name) / 'policy.json'
        policy_path.write_text(self.service.policy.model_dump_json(), encoding='utf-8')
        selections = Path(self.temp.name) / 'selections.json'
        selections.write_text(json.dumps([self.selection]), encoding='utf-8')
        output = StringIO()
        with redirect_stdout(output):
            code = main(['--db', str(self.path), '--policy', str(policy_path), '--subject', 'admin',
                '--context', 'session', 'propose-aimpro-bindings', self.source.model_dump_json(), str(selections)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())['fields']['status'], 'AWAITING_DECISION')
        self.assertEqual(self.store.read_context('session'), self.root)
