"""Executable architecture acceptance: production services, simulated model outputs.

Release, delivery import and activation use the production commands. The only
simulated boundary they add is the future runtime assessor role (G7): owner
decision D4 keeps activation refused while an ASSESS activity has no such role,
so the runtime scenarios patch one explicit EVALUATOR worker into the import.
"""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from learning.assessment import derive_activity_status, validate_evaluation
from learning.authoring import (ArtifactSelection, ProjectManifest, dependency_findings,
                               prepare_release, released_entities, review_receipt)
from learning.contracts import EntityRef, entity_data
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.releases import ActivationRefused
from learning.service import LearningService
from learning.store import LearningStore
from tests.authoring_cycle_fixtures import (AUTH, DELIVERY, DELIVERY_TWO, ProductionAuthoring,
    SimulatedRuntimeAgents, entity, ref, trusted_policy)


SIMULATED_ASSESSOR = {'EVALUATOR': 'learner-response-evaluator'}


class AuthoringCycleTest(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(target, side_effect=AssertionError('Architecture acceptance must not use the network'))
            blocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(blocked.assert_not_called)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LearningStore(Path(self.temp.name) / 'architecture.sqlite')
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), trusted_policy(), Mock())
        for context_id in (AUTH, DELIVERY, DELIVERY_TWO):
            self.service.bootstrap(context_id, 'admin')
        self.authoring = ProductionAuthoring(self.service)
        self.delivery = None
        self.runtime = None

    def build_project(self):
        author = self.authoring
        author.curator()
        for kind in ('ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'):
            proposal = author.generate(kind)
            with self.assertRaises(ValueError):
                prepare_release(self.store, author.context(), author.project, author.domain.ref)
            if kind == 'ASSESSMENT':
                with self.assertRaises(ValueError):
                    author.generate('TEACHER_CONTENT', 'pending-assessment')
            author.review_and_apply(AUTH, proposal, 'approve-' + kind)
            if kind != 'TRAINER_CONTENT':
                with self.assertRaises(ValueError):
                    author.release('pending-' + kind)
        author.configure_completion()
        return author

    def import_and_activate(self, release, context_id=DELIVERY, request_id='import-1'):
        """Production import, destination review, policy installation and activation."""
        author = self.authoring
        with patch.dict('learning.releases.RUNTIME_WORKERS', SIMULATED_ASSESSOR):
            result = author.delivery_import(release, context_id, request_id)
        self.assertEqual((result.preview.mode, result.preview.status), ('PREPARATION', 'DRAFT'))
        self.assertNotEqual(result.policy_preview, self.service.policy)
        self.assertEqual(self.store.read_context(context_id).fields['models'], [])
        author.review_and_apply(context_id, self.store.read(result.proposal, owner=context_id), request_id)
        root = self.store.read_context(context_id)
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        with self.assertRaises(ActivationRefused):
            self.service.propose_activation(context_id, 'admin', {'base_context': root.ref},
                                            request_id='activate-' + request_id)
        # The operator installs the exact approved preview for this delivery only.
        delivery = LearningService(self.store, load_contract(), result.policy_preview,
            Mock(side_effect=AssertionError('Activation must not construct agents')))
        activation = delivery.propose_activation(context_id, 'admin', {'base_context': root.ref},
                                                 request_id='activate-' + request_id)
        self.assertEqual(self.store.read_context(context_id), root)
        author.review_and_apply(context_id, self.store.read(activation.proposal, owner=context_id),
                                'activate-' + request_id, service=delivery)
        return delivery

    def publish_and_activate(self):
        author = self.build_project()
        release_proposal, release = author.release()
        with self.assertRaises(ValueError):
            author.delivery_import(release)
        author.review_and_apply(AUTH, release_proposal, 'publish-1')
        self.delivery = self.import_and_activate(release)
        context = self.delivery._context(DELIVERY, 'admin')
        self.assertEqual((context.snapshot.context.fields['mode'], context.snapshot.context.fields['status']),
                         ('LEARNING', 'ACTIVE'))
        self.runtime = SimulatedRuntimeAgents(self.delivery, self.authoring)
        return release

    def submit(self, activity_id, request_id):
        activity_id = self.authoring.activities[activity_id].id
        context = self.delivery._context(DELIVERY, 'learner')
        activity = next(e for e in context.snapshot.active_domain() if e.id == activity_id)
        return self.delivery.submit(DELIVERY, 'learner', activity.ref,
            'Synthetic attempt: write a polite reminder to fictional Alex about EXAMPLE-01. '
            'The fictional audience supplies context; the polite tone constrains the response.', request_id)

    def delivery_state(self, context_id):
        """Every stored record a delivery owns, plus its pinned definitions."""
        root = self.store.read_context(context_id)
        owned = {kind: [entity_data(e) for e in self.store.owned(context_id, kind)] for kind in (
            'ActivityOccurrence', 'LearningEvidence', 'LearningState', 'Evaluation', 'ResourceBinding',
            'ChangeProposal', 'HumanDecision', 'StateChange')}
        context = self.delivery._context(context_id, 'admin')
        pinned = sorted((entity_data(e) for e in context.snapshot.active_domain()), key=lambda e: (e['type'], e['id']))
        return entity_data(root), owned, pinned

    def test_full_authoring_release_delivery_and_reviewed_evaluation_cycle(self):
        release = self.publish_and_activate()
        author = self.authoring
        # The syllabus remains approved when the current composite design changes.
        with self.assertRaises(ValueError):
            self.service.approved_aimpro_syllabus(AUTH, 'admin', author.outline.ref)
        receipt = review_receipt(self.store, author.context(), author.syllabus)
        self.assertEqual(receipt.proposal.id, author.initial_receipt.proposal.id)
        before = self.store.read_context(DELIVERY)
        teacher_request, teacher = self.runtime.request('course:explain', 'EXPLAIN', 'teacher-1')
        self.assertEqual(teacher.kind, 'ANSWER')
        self.assertEqual(self.store.read_context(DELIVERY), before)
        self.delivery.orchestrator_factory = Mock(side_effect=AssertionError('Replay must not construct agents'))
        self.assertEqual(self.delivery.request(teacher_request), teacher)
        practice = self.submit('course:practice', 'practice-1')
        self.assertEqual(self.submit('course:practice', 'practice-1'), practice)
        _, feedback = self.runtime.request('course:practice', 'PRACTICE', 'trainer-1', practice)
        self.assertEqual(feedback.kind, 'ANSWER')
        observed = self.submit('course:assess', 'assessment-1')
        proposal = self.runtime.assessor_proposal(observed, 'evaluator-1')
        self.assertEqual(proposal.fields['status'], 'AWAITING_DECISION')
        self.assertFalse(self.store.read_context(DELIVERY).fields['learningStates'])
        candidate = next(e for e in proposal_candidates(self.store, proposal) if e.type == 'Evaluation')
        self.assertEqual(candidate.fields['evidence'], [ref(observed)])
        self.assertFalse(validate_evaluation(candidate, self.delivery._context(DELIVERY, 'admin').snapshot))
        with self.assertRaises(ValueError):
            self.delivery.apply(DELIVERY, 'admin', proposal.ref, 'unapproved-evaluation')
        author.review_and_apply(DELIVERY, proposal, 'review-evaluation', service=self.delivery)
        context = self.delivery._context(DELIVERY, 'learner')
        state = context.snapshot.get(context.snapshot.context.fields['learningStates'][0])
        self.assertEqual((state.fields['progress'], state.fields['verification']), ('IN_PROGRESS', 'UNVERIFIED'))
        occurrences = [context.snapshot.get(r) for r in context.snapshot.context.fields['activityOccurrences']]
        self.assertEqual([e.fields['status'] for e in occurrences], ['IN_PROGRESS', 'IN_PROGRESS'])
        phase = context.snapshot.get(context.snapshot.get(context.snapshot.context.fields['learningDesign']).fields['root'])
        self.assertEqual(derive_activity_status(phase, context.snapshot, context.snapshot.rule_bindings,
            learner_ref=context.participant.ref), 'IN_PROGRESS')
        self.assertEqual(self.runtime.events, ['lesson-explainer', 'guided-practice-coach', 'simulated-assessor-evaluator'])
        self.assertEqual(len(self.runtime.scopes), 2)
        self.assertEqual(len(self.store.owned(DELIVERY, 'LearningEvidence')), 2)
        self.assertEqual(self.store.read_context(AUTH).fields['mode'], 'PREPARATION')
        # Existing trace export also accepts the shared immutable release definitions.
        from aimpro.audit import DEFAULT_PROJECT
        trace = self.delivery.export_aimpro_trace(DELIVERY, 'admin', DEFAULT_PROJECT)
        self.assertFalse(trace['diagnostics'])

    def test_learner_request_cannot_persist_an_evaluator_change_proposal(self):
        self.publish_and_activate()
        observed = self.submit('course:assess', 'assessment-only')
        before = self.store.owned(DELIVERY, 'ChangeProposal')
        _, result = self.runtime.request('course:assess', 'ASSESS', 'forbidden-proposal', observed)
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(self.store.owned(DELIVERY, 'ChangeProposal'), before)
        self.assertFalse(self.store.owned(DELIVERY, 'Evaluation'))
        self.assertFalse(self.store.read_context(DELIVERY).fields['learningStates'])
        self.assertNotIn('propose', self.delivery.policy.subjects['learner'].actions[DELIVERY])

    def test_dependency_revision_rebuild_and_new_release_preserve_running_history(self):
        release_one = self.publish_and_activate()
        observed = self.submit('course:assess', 'old-attempt')
        evaluation = self.runtime.assessor_proposal(observed, 'old-evaluation')
        self.authoring.review_and_apply(DELIVERY, evaluation, 'old-evaluation', service=self.delivery)
        delivery_before = self.store.read_context(DELIVERY)
        history_before = self.delivery_state(DELIVERY)
        old_context = self.delivery._context(DELIVERY, 'admin')
        old_activity = old_context.snapshot.get(observed.fields['activity'])
        old_spec = old_context.snapshot.get(old_activity.fields['assessmentSpec'])
        author = self.authoring
        revision = author.generate('ASSESSMENT', '2')
        author.review_and_apply(AUTH, revision, 'revise-assessment')
        project = ProjectManifest.model_validate_json(author.project.fields['contentOrLocator'])
        self.assertEqual({f.target for f in dependency_findings(project)}, {'teacher_content', 'trainer_content'})
        with self.assertRaisesRegex(ValueError, 'stale'):
            author.release('2')
        self.assertEqual(review_receipt(self.store, author.context(), author.syllabus).proposal.id,
                         author.initial_receipt.proposal.id)
        for role in ('teacher', 'trainer'):
            revision = author.generate(role.upper() + '_CONTENT', '2')
            author.review_and_apply(AUTH, revision, 'revise-' + role)
        author.configure_completion('2')
        _, release_two = author.release('2', approve=True)
        # The running delivery cannot be switched to release 2 without a reviewed migration.
        with self.assertRaisesRegex(ValueError, 'migration'):
            author.delivery_import(release_two, DELIVERY, 'import-2', service=self.delivery)
        self.import_and_activate(release_two, DELIVERY_TWO, 'import-2')
        self.assertEqual(self.store.read_context(DELIVERY), delivery_before)
        self.assertEqual(self.delivery_state(DELIVERY), history_before)
        self.assertEqual(self.store.read(observed.ref, owner=DELIVERY), observed)
        with self.store.db:
            self.store.db.execute('BEGIN')
            one, definitions_one = released_entities(self.store, author.context(), release_one)
            two, definitions_two = released_entities(self.store, author.context(), release_two)
        self.assertNotEqual(one.project, two.project)
        self.assertIn(old_spec, definitions_one)
        self.assertNotIn(old_spec, definitions_two)
        new_spec = next(e for e in definitions_two if e.id == old_spec.id)
        evaluation = entity('Evaluation', 'historical-evaluation', {'context': ref(delivery_before),
            'evidence': [ref(observed)], 'specification': ref(old_spec), 'mode': 'FORMATIVE',
            'result': 'Synthetic historical observation.', 'reviewPayloadKey': 'pending', 'criterionJudgments': [{
                'criterionKey': 'clarity', 'levelKey': 'clear', 'evidenceRefs': [ref(observed)], 'reason': 'Observed fictional task.'}]})
        self.assertFalse(validate_evaluation(evaluation, old_context.snapshot))
        changed = evaluation.model_copy(update={'fields': {**evaluation.fields, 'specification': ref(new_spec)}})
        snapshot = replace(old_context.snapshot, entities={**old_context.snapshot.entities, new_spec.ref: new_spec})
        self.assertTrue(validate_evaluation(changed, snapshot))
        self.assertEqual(self.submit('course:assess', 'old-attempt'), observed)


class ProjectDependencyContractTest(unittest.TestCase):
    def project(self, artifacts):
        return ProjectManifest(project_id='test', authoring_context='owner',
            design=EntityRef(type='LearningDesign', id='design', version='1'),
            required_kinds=('SOURCE',), artifacts=tuple(artifacts))

    def artifact(self, key, dependencies=(), version='1'):
        return ArtifactSelection(key=key, kind='SOURCE',
            resource=EntityRef(type='Resource', id=key, version=version), depends_on=tuple(dependencies))

    def test_missing_versions_propagate_staleness_without_changing_prior_selection(self):
        old = self.artifact('input')
        syllabus = self.artifact('syllabus', (old.resource,))
        content = self.artifact('content', (syllabus.resource,))
        original = self.project((old, syllabus, content))
        changed = self.project((self.artifact('input', version='2'), syllabus, content))
        self.assertFalse(dependency_findings(original))
        self.assertEqual({f.target for f in dependency_findings(changed)}, {'syllabus', 'content'})
        self.assertFalse(dependency_findings(original))

    def test_cycles_duplicate_identities_and_latest_references_are_rejected(self):
        first, second = self.artifact('a'), self.artifact('b')
        cycle = self.project((self.artifact('a', (second.resource,)), self.artifact('b', (first.resource,))))
        self.assertEqual({f.target for f in dependency_findings(cycle)}, {'a', 'b'})
        with self.assertRaises(ValueError):
            self.project((first, first.model_copy(update={'key': 'alias'})))
        with self.assertRaises(ValueError):
            self.artifact('a', version='latest')
