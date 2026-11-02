from dataclasses import replace
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import json
from uuid import uuid4
import unittest

from learning.context import LearningRequest
from learning.contracts import EntityRef
from learning.decisions import approval_valid
from learning.planning import Capability, LearningStepDraft, _scope
from learning.policies import TrustedPolicy
from agent_system.plan import PlanStep, RetrievalRequest
from learning.service import LearningService
from learning.validation import check_readiness
from learning.rules import evaluate_rule


class ExecutionSetupTest(unittest.TestCase):
    def setUp(self):
        from tests.test_aimpro_bindings import AimproBindingTest
        AimproBindingTest.setUp(self)
        selections = [{**self.selection, 'activity': e.ref.model_dump(),
                       'requirement': e.fields['resourceRequirements'][0]}
                      for e in self.saved if e.type == 'ActivityDefinition']
        proposal = self.service.propose_aimpro_bindings('session', 'admin', self.source, selections)
        self.service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Reviewed fixture resources')
        self.service.apply('session', 'admin', proposal.ref, 'initial-bindings')
        self.initial = self.store.read_context('session')

    def prepare(self):
        return self.service.prepare_aimpro_execution('session', 'admin', learner='learner', scope_name='learning-session')

    def apply_setup(self):
        result = self.prepare()
        ref = EntityRef.model_validate({k: result['proposal'][k] for k in ('type', 'id', 'version')})
        self.service.decide('session', 'admin', ref, 'APPROVE', 'Reviewed worker, completion and policy fixture')
        self.service.apply('session', 'admin', ref, 'setup')
        next_policy = TrustedPolicy.model_validate(result['policy_preview'])
        return LearningService(self.store, self.service.contract, next_policy, lambda: None), result

    def test_setup_is_a_proposal_with_an_isolated_exact_key_policy(self):
        original_policy = self.service.policy.model_dump(mode='json')
        result = self.prepare()
        self.assertEqual(self.store.read_context('session'), self.initial)
        self.assertEqual(self.service.policy.model_dump(mode='json'), original_policy)
        preview = TrustedPolicy.model_validate(result['policy_preview'])
        scope = preview.scopes['learning-session']
        self.assertEqual(scope.contexts, ['session'])
        self.assertEqual(scope.sources, [])
        self.assertEqual(scope.resources, ['["wp3:test","v1"]'])
        self.assertNotIn('learner', preview.scopes['wp3'].subjects)
        self.assertEqual(set(preview.subjects['learner'].roles), {'LEARNER'})
        self.assertNotIn('decide', preview.subjects['learner'].actions['session'])
        self.assertEqual(result['preview']['eligible_workers'], ['guided-practice-coach', 'lesson-explainer'])
        self.assertTrue(all(f['code'] == 'R08' for f in result['preview']['readiness_findings']))

    def test_approval_switches_policy_version_but_does_not_activate_or_assign_progress(self):
        service, result = self.apply_setup()
        with self.assertRaises(ValueError):
            self.service._context('session', 'admin')
        context = service._context('session', 'learner')
        self.assertEqual(context.snapshot.context.fields['mode'], 'PREPARATION')
        self.assertEqual(context.snapshot.context.fields['status'], 'DRAFT')
        self.assertFalse(context.snapshot.context.fields['learningStates'])
        self.assertEqual(len(context.snapshot.rule_bindings), 2)
        self.assertTrue(all(approval_valid(context.snapshot.get(r), context.snapshot, service.policy)
                            for r in context.snapshot.context.fields['resourceBindings']))
        self.assertFalse(check_readiness(context.snapshot, context.snapshot.context.fields['learningDesign'], 'advance',
            learner_ref=context.participant.ref, policy=service.policy, subject_key='learner'))
        unit = next(e for e in context.snapshot.active_domain() if e.type == 'ProcessNode' and e.fields['kind'] == 'UNIT')
        rule = EntityRef.model_validate(unit.fields['completionRule'])
        statuses = {r['id']: 'COMPLETED' for r in unit.fields['activities']}
        self.assertEqual(evaluate_rule(rule, context.snapshot, statuses, context.snapshot.rule_bindings), 'SATISFIED')
        statuses[next(iter(statuses))] = 'SKIPPED'
        self.assertEqual(evaluate_rule(rule, context.snapshot, statuses, context.snapshot.rule_bindings), 'NOT_SATISFIED')
        self.assertEqual(evaluate_rule(rule, context.snapshot, {}, context.snapshot.rule_bindings), 'UNKNOWN')
        with self.assertRaises(ValueError):
            service.prepare_aimpro_execution('session', 'admin', learner='learner', scope_name='another-learning-scope')

    def test_an_explicit_fixture_activation_allows_scoped_topic_retrieval(self):
        service, _ = self.apply_setup()
        root = self.store.read_context('session')
        active = root.model_copy(update={'version': uuid4().hex, 'fields': {**root.fields, 'mode': 'LEARNING', 'status': 'ACTIVE'}})
        proposal = service.propose('session', 'admin', (root.ref,), (active,), 'Explicit fixture-only activation')
        service.decide('session', 'admin', proposal.ref, 'APPROVE', 'Reviewed fixture activation')
        service.apply('session', 'admin', proposal.ref, 'activate')
        context = service._context('session', 'learner')
        activity = next(e for e in context.snapshot.active_domain() if e.type == 'ActivityDefinition')
        outcome = context.snapshot.get(activity.fields['outcomes'][0])
        topic = EntityRef.model_validate(outcome.fields['topics'][0])
        request = LearningRequest(request_id='retrieval-check', context_ref=context.snapshot.context.ref,
            subject_key='learner', text='Explain the prompt choices', intent='EXPLAIN',
            activity_refs=(activity.ref,), topic_refs=(topic,))
        context = replace(context, request=request)
        profile = next(e for e in context.snapshot.active_domain() if e.type == 'AgentSpecialization')
        draft = LearningStepDraft(step=PlanStep(id='explain', agent='lesson-explainer', task='Explain',
            retrieval=RetrievalRequest(tool='search_documents', query='prompting', k=1)),
            specialization=profile.ref, intent='EXPLAIN', expected_output='EXPLANATION', activities=(activity.ref,),
            required_capabilities=(Capability(capability='search_documents', accessPath='ORCHESTRATOR_RETRIEVAL',
                operations=('read',), scope='learning-session', purpose='Use the approved workshop source'),))
        scope, sources = _scope(context, draft)
        self.assertEqual(scope.resource_keys, ('["wp3:test","v1"]',))
        self.assertEqual(len(sources), 1)
        self.assertNotIn(topic.model_dump(), sources[0].fields['topics'])
        outside = request.model_copy(update={'topic_refs': (EntityRef(type='Topic', id='unrelated', version='1'),)})
        self.assertEqual(_scope(replace(context, request=outside), draft)[0].resource_keys, ())

    def test_scope_revocation_and_nonlearner_selection_are_rejected(self):
        self.service.policy = self.service.policy.model_copy(update={'scopes': {}})
        with self.assertRaises(ValueError):
            self.prepare()
        with self.assertRaises(ValueError):
            self.service.prepare_aimpro_execution('session', 'admin', learner='admin')

    def test_existing_policy_scope_cannot_be_overwritten(self):
        for scope_name in ('wp3', ' learning-session ', ''):
            with self.assertRaises(ValueError):
                self.service.prepare_aimpro_execution('session', 'admin', learner='learner', scope_name=scope_name)

    def test_uncovered_activity_intent_is_rejected_before_proposal_storage(self):
        from aimpro.execution_setup import prepare_execution
        context = self.service._context('session', 'admin')
        activity = next(e for e in context.snapshot.active_domain() if e.type == 'ActivityDefinition')
        changed = activity.model_copy(update={'fields': {**activity.fields, 'intent': 'ASSESS'}})
        snapshot = replace(context.snapshot, entities={**context.snapshot.entities, changed.ref: changed})
        count = len(self.store.owned('session', 'ChangeProposal'))
        with self.assertRaisesRegex(ValueError, 'not covered'):
            prepare_execution(self.store, replace(context, snapshot=snapshot), learner='learner')
        self.assertEqual(len(self.store.owned('session', 'ChangeProposal')), count)

    def test_cli_writes_only_a_new_policy_preview_and_does_not_activate(self):
        from learning.__main__ import main
        original = Path(self.temp.name) / 'current-policy.json'
        original.write_text(self.service.policy.model_dump_json(), encoding='utf-8')
        preview = Path(self.temp.name) / 'next-policy.json'
        args = ['--db', str(self.path), '--policy', str(original), '--subject', 'admin', '--context', 'session',
                'prepare-aimpro-execution', '--learner', 'learner', '--learning-scope', 'learning-session',
                '--policy-preview', str(preview)]
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(json.loads(preview.read_text()), result['policy_preview'])
        self.assertEqual(self.store.read_context('session'), self.initial)
        self.assertEqual(TrustedPolicy.model_validate_json(original.read_text()), self.service.policy)
        count = len(self.store.owned('session', 'ChangeProposal'))
        with redirect_stderr(StringIO()):
            self.assertEqual(main(args), 2)
        self.assertEqual(len(self.store.owned('session', 'ChangeProposal')), count)
