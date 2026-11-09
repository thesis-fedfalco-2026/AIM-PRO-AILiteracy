"""Production release, delivery-import and activation acceptance for R1 (#71).

Temporary SQLite file or PostgreSQL test schema only; sockets, DNS (except for
the configured PostgreSQL test host) and model construction are forbidden. Model
responses for the authoring generators are synthetic; every release, import and
activation step runs the production commands and the generic decide/apply.
"""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from learning.__main__ import main
from learning.authoring import ProjectManifest, ReleaseManifest, released_entities, review_receipt
from learning.contracts import EntityRef, entity_data
from learning.decisions import approval_valid, create_proposal, proposal_candidates, save_proposal
from learning.metamodel import load_contract
from learning.policies import RuleBinding, TrustedPolicy
from learning.releases import ActivationRefused, DeliveryImport, ReleaseCommand
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from tests.authoring_cycle_fixtures import (AUTH, DELIVERY, DELIVERY_TWO, ProductionAuthoring,
                                            entity, ref, trusted_policy)
from tests.store_backends import block_network, new_store_location, on_both_backends


SIMULATED_ASSESSOR = {'EVALUATOR': 'learner-response-evaluator'}


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        block_network(self, 'Release tests must not use the network or models',
                      'crewai.LLM', 'agent_system.runtime.LLMFactory.__call__')
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = new_store_location(self, self.temp.name, 'releases.sqlite')
        self.store = LearningStore(self.path)
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), trusted_policy(),
            Mock(side_effect=AssertionError('Release commands must not construct agents')))
        for context_id in (AUTH, DELIVERY, DELIVERY_TWO):
            self.service.bootstrap(context_id, 'admin')
        self.author = ProductionAuthoring(self.service)

    def build(self, completion=True):
        author = self.author
        author.curator()
        for kind in ('ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'):
            author.review_and_apply(AUTH, author.generate(kind), 'approve-' + kind)
        if completion:
            author.configure_completion()
        return author

    def command(self, **changes):
        values = {'project': self.author.project.ref, 'domain': self.author.domain.ref,
                  'base_context': self.store.read_context(AUTH).ref}
        return ReleaseCommand(**{**values, **changes})

    def released(self):
        self.build()
        proposal, release = self.author.release(approve=True)
        return release

    def install(self, result):
        return LearningService(self.store, load_contract(), result.policy_preview,
            Mock(side_effect=AssertionError('Release commands must not construct agents')))

    def imported(self, release, context_id=DELIVERY, request_id='import-1', **options):
        result = self.author.delivery_import(release, context_id, request_id, **options)
        self.author.review_and_apply(context_id, self.store.read(result.proposal, owner=context_id), request_id)
        return result, self.install(result)

    def activation(self, service, context_id=DELIVERY, request_id='activate'):
        return service.propose_activation(context_id, 'admin',
            {'base_context': self.store.read_context(context_id).ref}, request_id=request_id)


    def seed_history(self, context_id):
        """Synthetic legacy learner history; no production path writes it in DRAFT."""
        root = self.store.read_context(context_id)
        learner = next(r for r in root.fields['participants'] if r['id'].endswith(':learner'))
        evidence = entity('LearningEvidence', context_id + ':legacy-evidence', {
            'context': ref(root), 'learner': learner, 'activity': {'type': 'ActivityDefinition', 'id': 'legacy', 'version': '1'},
            'occurrence': {'type': 'ActivityOccurrence', 'id': 'legacy', 'version': '1'}, 'outcomes': [ref(self.author.outcome)],
            'kind': 'CRITERIA_BASED_PRODUCT', 'contentOrLocator': 'Legacy observed attempt.',
            'observedAt': '2026-11-08T00:00:00+00:00'})
        with self.store.db:
            self.store._put(evidence.model_copy(update={'provenance': evidence.provenance.model_copy(
                update={'origin': 'OBSERVED_EVENT'})}), context_id)


@on_both_backends
class ReleaseProposalTest(ReleaseTest):
    def test_release_proposal_is_pending_exact_and_replays(self):
        self.build()
        before = self.store.read_context(AUTH)
        result = self.service.propose_release(AUTH, 'admin', self.command(), request_id='release')
        self.assertEqual(self.store.read_context(AUTH), before)
        proposal = self.store.read(result.proposal, owner=AUTH)
        self.assertEqual(proposal.fields['status'], 'AWAITING_DECISION')
        saved = {c.type: c for c in proposal_candidates(self.store, proposal)}
        self.assertEqual(set(saved), {'Resource', 'DomainModel', 'ExecutionContext'})
        self.assertEqual(ReleaseManifest.model_validate_json(saved['Resource'].fields['contentOrLocator']), result.manifest)
        self.assertEqual(saved['Resource'].fields['derivedFrom'], [ref(self.author.project)])
        self.assertEqual(saved['DomainModel'].fields['definitions'], [result.release.model_dump()])
        self.assertEqual((saved['ExecutionContext'].fields['mode'], saved['ExecutionContext'].fields['status']),
                         ('PREPARATION', 'DRAFT'))
        project = ProjectManifest.model_validate_json(self.author.project.fields['contentOrLocator'])
        self.assertEqual(result.manifest.artifacts, tuple(a.resource for a in project.artifacts))
        with patch('learning.releases.prepare_release', side_effect=AssertionError('Replay must not rebuild')):
            self.assertEqual(self.service.propose_release(AUTH, 'admin', self.command(base_context=before.ref),
                                                          request_id='release'), result)
        with self.assertRaises(StateConflict):
            self.service.propose_release(AUTH, 'admin', self.command(base_context=before.ref,
                domain=self.author.base_domain.ref), request_id='release')
        self.author.review_and_apply(AUTH, proposal, 'release')
        self.assertEqual(self.service.propose_release(AUTH, 'admin', self.command(base_context=before.ref),
                                                      request_id='release'), result)
        root = self.store.read_context(AUTH)
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        self.assertIn(result.catalogue.model_dump(), root.fields['models'])
        self.assertFalse(self.store.owned(DELIVERY, 'ChangeProposal'))

    def test_release_refuses_latest_incomplete_stale_foreign_and_unreviewed_inputs(self):
        author = self.author
        author.curator()
        author.review_and_apply(AUTH, author.generate('ASSESSMENT'), 'assessment')
        with self.assertRaisesRegex(ValueError, 'missing or stale'):
            self.service.propose_release(AUTH, 'admin', self.command(), request_id='incomplete')
        for kind in ('TEACHER_CONTENT', 'TRAINER_CONTENT'):
            author.review_and_apply(AUTH, author.generate(kind), 'approve-' + kind)
        latest = author.project.ref.model_copy(update={'version': 'latest'})
        with self.assertRaises(ValueError):
            self.service.propose_release(AUTH, 'admin', self.command(project=latest), request_id='latest')
        with self.assertRaisesRegex(ValueError, 'consistent selected definitions'):
            self.service.propose_release(AUTH, 'admin', self.command(domain=author.base_domain.ref), request_id='curator')
        # A domain owned by another context is outside the authoring snapshot.
        topic = entity('Topic', 'delivery:foreign-topic', author.topic.fields)
        foreign = entity('DomainModel', 'delivery:foreign-domain', {'name': 'Foreign', 'scope': 'Another context',
                                                                    'topics': [ref(topic)], 'definitions': []})
        root = self.store.read_context(DELIVERY)
        updated = entity('ExecutionContext', DELIVERY, {**root.fields, 'models': [ref(foreign)]}, 'foreign')
        author.review_and_apply(DELIVERY, self.service.propose(DELIVERY, 'admin', (root.ref,), (topic, foreign, updated),
                                'Synthetic foreign domain'), 'foreign')
        with self.assertRaisesRegex(ValueError, 'outside the authorized snapshot'):
            self.service.propose_release(AUTH, 'admin', self.command(domain=foreign.ref), request_id='foreign')
        # A similar domain in this context was never reviewed with the project.
        unrelated = entity('DomainModel', 'course:unrelated-domain', author.domain.fields)
        root = self.store.read_context(AUTH)
        updated = entity('ExecutionContext', AUTH, {**root.fields, 'models': [*root.fields['models'], ref(unrelated)]}, 'unrelated')
        author.review_and_apply(AUTH, self.service.propose(AUTH, 'admin', (root.ref,), (unrelated, updated),
                                'Synthetic unrelated domain'), 'unrelated')
        with self.assertRaisesRegex(ValueError, 'not reviewed with this project'):
            self.service.propose_release(AUTH, 'admin', self.command(domain=unrelated.ref), request_id='unrelated')
        # A superseded dependency makes dependants stale.
        author.review_and_apply(AUTH, author.generate('ASSESSMENT', '2'), 'assessment-2')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.service.propose_release(AUTH, 'admin', self.command(), request_id='stale')
        self.assertFalse([r for r in self.store.read_context(AUTH).fields['models'] if r['id'].startswith('authoring-release:')])

    def test_application_refuses_a_changed_authoring_context_or_project_base(self):
        author = self.build()
        result = self.service.propose_release(AUTH, 'admin', self.command(), request_id='release')
        proposal = self.store.read(result.proposal, owner=AUTH)
        self.service.decide(AUTH, 'admin', proposal.ref, 'APPROVE', 'Synthetic release review')
        model = entity('DomainModel', 'course:unrelated-model', {'name': 'Unrelated', 'scope': 'Unrelated',
                                                                 'topics': [ref(author.topic)], 'definitions': []})
        root = self.store.read_context(AUTH)
        updated = entity('ExecutionContext', AUTH, {**root.fields, 'models': [*root.fields['models'], ref(model)]}, 'edit')
        author.review_and_apply(AUTH, self.service.propose(AUTH, 'admin', (root.ref,), (model, updated),
                                'Unrelated context edit'), 'edit')
        with self.assertRaises(StateConflict):
            self.service.apply(AUTH, 'admin', proposal.ref, 'stale-release')
        # A newer project base also invalidates the next proposal before application.
        second = self.service.propose_release(AUTH, 'admin', self.command(), request_id='release-2')
        second = self.store.read(second.proposal, owner=AUTH)
        self.service.decide(AUTH, 'admin', second.ref, 'APPROVE', 'Synthetic release review')
        author.review_and_apply(AUTH, author.generate('ASSESSMENT', '2'), 'assessment-2')
        with self.assertRaises(StateConflict):
            self.service.apply(AUTH, 'admin', second.ref, 'stale-project')
        self.assertFalse([r for r in self.store.read_context(AUTH).fields['models'] if r['id'].startswith('authoring-release:')])


@on_both_backends
class ReleaseInspectionTest(ReleaseTest):
    def test_show_release_cites_receipts_closure_and_ignores_later_revisions(self):
        self.build()
        proposal, release = self.author.release()
        with self.assertRaisesRegex(ValueError, 'not applied'):
            self.service.inspect_release(AUTH, 'admin', release.ref)
        self.author.review_and_apply(AUTH, proposal, 'release')
        changes = self.store.db.total_changes
        view = self.service.inspect_release(AUTH, 'admin', release.ref)
        self.assertEqual(self.store.db.total_changes, changes)
        self.assertFalse(view.findings)
        self.assertEqual(view.receipt.proposal.id, proposal.id)
        self.assertEqual(view.receipt.decision.id, self.store.read(view.receipt.proposal, owner=AUTH).fields['decision']['id'])
        self.assertTrue(view.project_receipt and all(a.receipt for a in view.artifacts))
        self.assertEqual([a.resource for a in view.artifacts], list(view.manifest.artifacts))
        self.assertTrue({view.manifest.project, view.manifest.design, *view.manifest.artifacts} <= set(view.closure))
        self.assertEqual(list(view.closure), sorted(view.closure, key=lambda r: (r.type, r.id, r.version)))
        for item in view.closure:
            self.assertNotIn(item.version, {'latest', 'LATEST'})
        # A later authoring revision, even pending with a Lead ACCEPT, changes nothing.
        revision = self.author.generate('ASSESSMENT', '2')
        package = self.author.packages['ASSESSMENT']
        self.assertEqual(package.review.verdict, 'ACCEPT')
        artifact = next(c for c in proposal_candidates(self.store, revision)
                        if c.type == 'Resource' and c.id.startswith('authoring-output:'))
        with self.assertRaises(ValueError):
            review_receipt(self.store, self.author.context(), artifact)
        self.assertEqual(self.service.inspect_release(AUTH, 'admin', release.ref), view)
        self.author.review_and_apply(AUTH, revision, 'assessment-2')
        self.assertEqual(self.service.inspect_release(AUTH, 'admin', release.ref), view)
        # The store refuses a different payload for an existing (id, version).
        design = self.store.read(view.manifest.design, owner=AUTH)
        changed = design.model_copy(update={'fields': {**design.fields, 'name': 'Rewritten'}})
        with self.assertRaisesRegex(ValueError, 'immutable'):
            self.store._put(changed, None)

    def test_revoked_decision_authority_invalidates_receipts(self):
        release = self.released()
        policy = self.service.policy.model_dump()
        policy['subjects']['admin']['actions'][AUTH].remove('decide')
        revoked = LearningService(self.store, load_contract(), TrustedPolicy.model_validate(policy), Mock())
        view = revoked.inspect_release(AUTH, 'admin', release.ref)
        self.assertIsNone(view.receipt)
        self.assertIsNone(view.project_receipt)
        self.assertTrue(all(a.receipt is None for a in view.artifacts))
        self.assertIn('RELEASE_UNAPPROVED', {f.code for f in view.findings})
        with self.assertRaisesRegex(ValueError, 'approved and applied'):
            self.author.delivery_import(release, service=revoked)


@on_both_backends
class DeliveryImportTest(ReleaseTest):
    def test_import_requires_an_applied_release(self):
        self.build()
        proposal, release = self.author.release()
        command = DeliveryImport(release=release.ref, authoring_context=AUTH,
            base_context=self.store.read_context(DELIVERY).ref, scope_name='scope')
        with self.assertRaisesRegex(ValueError, 'not applied'):
            self.service.propose_delivery_import(DELIVERY, 'admin', command, request_id='unapplied')
        self.service.decide(AUTH, 'admin', proposal.ref, 'REJECT', 'Synthetic rejection')
        with self.assertRaisesRegex(ValueError, 'not applied'):
            self.service.propose_delivery_import(DELIVERY, 'admin', command, request_id='rejected')
        self.assertEqual(self.store.read_context(DELIVERY).fields['models'], [])

    def test_import_is_frozen_reviewed_and_keeps_the_destination_in_preparation(self):
        release = self.released()
        authoring = self.store.read_context(AUTH)
        destination = self.store.read_context(DELIVERY)
        result = self.author.delivery_import(release, scope='delivery-scope')
        # The proposal changes neither context, nor the trusted policy.
        self.assertEqual(self.store.read_context(AUTH), authoring)
        self.assertEqual(self.store.read_context(DELIVERY), destination)
        self.assertEqual(self.service.policy, trusted_policy())
        self.assertEqual((result.preview.mode, result.preview.status), ('PREPARATION', 'DRAFT'))
        self.assertNotIn('delivery-scope', self.service.policy.scopes)
        scope = result.policy_preview.scopes['delivery-scope']
        self.assertEqual(scope.contexts, [DELIVERY])
        self.assertEqual(tuple(scope.resources), result.preview.resource_keys)
        self.assertEqual(tuple(scope.activities), result.preview.activities)
        self.assertEqual(set(result.preview.workers), {'lesson-explainer', 'guided-practice-coach'})
        self.assertIn('R08', {f.code for f in result.preview.readiness_findings})
        proposal = self.store.read(result.proposal, owner=DELIVERY)
        for receipt in ('"release"', '"project"', '"artifacts"', 'proposal-', 'decision-', 'change-'):
            self.assertIn(receipt, proposal.fields['proposedChange'])
        saved = proposal_candidates(self.store, proposal)
        view = self.service.inspect_release(AUTH, 'admin', release.ref)
        for item in view.closure:
            frozen = next(c for c in saved if c.ref == item)
            self.assertEqual(entity_data(frozen), entity_data(self.store.read(item, owner=AUTH)))
        bindings = [c for c in saved if c.type == 'ResourceBinding']
        self.assertEqual(len(bindings), len(self.author.selections(release, 'delivery-scope')))
        # Authoring approval grants no destination use.
        context = self.service._context(DELIVERY, 'admin')
        authoring_decision = view.receipt.decision
        borrowed = bindings[0].model_copy(update={'fields': {**bindings[0].fields,
            'approvalDecision': authoring_decision.model_dump()}})
        self.assertFalse(approval_valid(borrowed, context.snapshot, self.service.policy))
        self.author.review_and_apply(DELIVERY, proposal, 'import')
        root = self.store.read_context(DELIVERY)
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        self.assertEqual(root.fields['learningDesign'], view.manifest.design.model_dump())
        self.assertEqual(root.fields['models'][0], view.manifest.domain.model_dump())
        self.assertEqual(root.fields['policies'], result.policy_preview.policy_ref.model_dump())
        self.assertEqual(self.store.read_context(AUTH), authoring)
        delivery = self.install(result)
        context = delivery._context(DELIVERY, 'admin')
        decision = next(d for d in self.store.owned(DELIVERY, 'HumanDecision'))
        for binding in (context.snapshot.get(r) for r in root.fields['resourceBindings']):
            self.assertEqual(binding.fields['approvalDecision'], decision.ref.model_dump())
            self.assertTrue(approval_valid(binding, context.snapshot, delivery.policy))
        # Replay is exact under the installed policy; a different command conflicts.
        command = DeliveryImport(release=release.ref, authoring_context=AUTH, base_context=destination.ref,
            scope_name='delivery-scope', bindings=self.author.selections(release, 'delivery-scope'),
            completion_handlers=self.handlers(view))
        self.assertEqual(delivery.propose_delivery_import(DELIVERY, 'admin', command, request_id='import-1'), result)
        with self.assertRaises(StateConflict):
            delivery.propose_delivery_import(DELIVERY, 'admin',
                command.model_copy(update={'scope_name': 'other'}), request_id='import-1')

    def handlers(self, view):
        return tuple(RuleBinding(rule=r, handler='all_completed') for r in view.closure
                     if r.type == 'RuleDefinition' and r.id.startswith('course:completion:'))

    def test_bindings_must_use_the_pinned_version_new_scope_and_exact_catalogue_resource(self):
        release = self.released()
        view = self.service.inspect_release(AUTH, 'admin', release.ref)
        selections = self.author.selections(release, 'scope')
        base = DeliveryImport(release=release.ref, authoring_context=AUTH,
            base_context=self.store.read_context(DELIVERY).ref, scope_name='scope', bindings=selections)
        def refused(pattern, **changes):
            with self.assertRaisesRegex(ValueError, pattern):
                self.service.propose_delivery_import(DELIVERY, 'admin', base.model_copy(update=changes),
                                                     request_id='refused')
        first = selections[0]
        other = first.model_copy(update={'resource': first.resource.model_copy(update={'version': 'other'})})
        refused('pinned', bindings=(other, *selections[1:]))
        refused('new reviewed delivery scope', bindings=(first.model_copy(update={'usage_scope': 'delivery'}),))
        refused('new scope name', scope_name='delivery', bindings=())
        outside = first.model_copy(update={'requirement': EntityRef(type='ResourceRequirement',
                                                                    id='course:unused', version='1')})
        refused('not used by the frozen design', bindings=(outside,))
        refused('at most one', bindings=(first, first))
        wp3 = next(s for s in selections if not s.resource.id.startswith('authoring-output:'))
        source = self.author.source.ref
        with patch('learning.releases._pins', return_value={wp3.requirement.id: source}):
            refused('exact catalogue resource', bindings=(wp3.model_copy(update={'resource': source}),))
        handlers = self.handlers(view)
        refused('Completion handlers', completion_handlers=(handlers[0], handlers[0]))
        self.assertFalse(self.store.owned(DELIVERY, 'ChangeProposal'))
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE owner=? AND id='refused'",
                                                (DELIVERY,)).fetchone())

    def test_learner_history_blocks_import_at_proposal_and_application(self):
        release = self.released()
        result = self.author.delivery_import(release, DELIVERY_TWO, 'import-two')
        proposal = self.store.read(result.proposal, owner=DELIVERY_TWO)
        self.service.decide(DELIVERY_TWO, 'admin', proposal.ref, 'APPROVE', 'Synthetic destination review')
        self.seed_history(DELIVERY_TWO)
        with self.assertRaisesRegex(ValueError, 'migration'):
            self.service.apply(DELIVERY_TWO, 'admin', proposal.ref, 'import-two')
        with self.assertRaisesRegex(ValueError, 'migration'):
            self.author.delivery_import(release, DELIVERY_TWO, 'import-again')
        self.assertEqual(self.store.read_context(DELIVERY_TWO).fields['models'], [])

@on_both_backends
class ActivationTest(ReleaseTest):
    def test_activation_is_refused_with_explicit_findings(self):
        release = self.released()
        selections = self.author.selections(release, 'partial')
        result, delivery = self.imported(release, scope='partial', omit=(selections[0].requirement.id,), handlers=False)
        root = self.store.read_context(DELIVERY)
        # Without the installed preview, the context cannot even be loaded for activation.
        with self.assertRaises(ActivationRefused) as refused:
            self.activation(self.service)
        self.assertEqual([f.code for f in refused.exception.findings], ['RELEASE_POLICY_NOT_INSTALLED'])
        edited = result.policy_preview.model_dump(mode='json')
        edited['scopes']['partial']['resources'] = []
        tampered = LearningService(self.store, load_contract(), TrustedPolicy.model_validate(edited), Mock())
        with self.assertRaises(ActivationRefused) as refused:
            self.activation(tampered)
        self.assertIn('RELEASE_POLICY_NOT_INSTALLED', {f.code for f in refused.exception.findings})
        with self.assertRaises(ActivationRefused) as refused:
            self.activation(delivery)
        findings = refused.exception.findings
        codes = {f.code for f in findings}
        self.assertTrue({'R08', 'RELEASE_COMPLETION_HANDLER', 'RELEASE_RUNTIME_ROLE'} <= codes, codes)
        self.assertNotIn('RELEASE_POLICY_NOT_INSTALLED', codes)
        assess = {a.id for a in delivery._context(DELIVERY, 'admin').snapshot.active_domain()
                  if a.type == 'ActivityDefinition' and a.fields['intent'] == 'ASSESS'}
        roles = {f.target for f in findings if f.code == 'RELEASE_RUNTIME_ROLE'}
        self.assertEqual(roles, assess)
        self.assertTrue(all('D4' in f.reason for f in findings if f.code == 'RELEASE_RUNTIME_ROLE'))
        self.assertEqual(self.store.read_context(DELIVERY), root)
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE owner=? AND id='activate'",
                                                (DELIVERY,)).fetchone())

    def test_assess_activities_keep_activation_refused_without_a_runtime_role(self):
        release = self.released()
        _, delivery = self.imported(release)
        with self.assertRaises(ActivationRefused) as refused:
            self.activation(delivery)
        self.assertEqual({f.code for f in refused.exception.findings}, {'RELEASE_RUNTIME_ROLE'})

    def test_activation_proposes_learning_active_only_and_generic_activation_is_reserved(self):
        release = self.released()
        with patch.dict('learning.releases.RUNTIME_WORKERS', SIMULATED_ASSESSOR):
            _, delivery = self.imported(release)
        root = self.store.read_context(DELIVERY)
        active = entity('ExecutionContext', DELIVERY, {**root.fields, 'mode': 'LEARNING', 'status': 'ACTIVE'}, 'generic')
        with self.assertRaisesRegex(ValueError, 'dedicated commands'):
            delivery.propose(DELIVERY, 'admin', (root.ref,), (active,), 'Generic activation attempt')
        context = delivery._context(DELIVERY, 'admin')
        bypass = create_proposal(context, (root.ref,), (active,), 'Direct activation bypass')
        save_proposal(self.store, context, bypass, (active,))
        delivery.decide(DELIVERY, 'admin', bypass.ref, 'APPROVE', 'Synthetic review of a bypass')
        with self.assertRaisesRegex(ValueError, 'dedicated commands'):
            delivery.apply(DELIVERY, 'admin', bypass.ref, 'bypass')
        base = {'base_context': root.ref}
        result = delivery.propose_activation(DELIVERY, 'admin', base, request_id='activate')
        self.assertEqual(delivery.propose_activation(DELIVERY, 'admin', base, request_id='activate'), result)
        proposal = self.store.read(result.proposal, owner=DELIVERY)
        (candidate,) = proposal_candidates(self.store, proposal)
        changed = {k for k in root.fields if root.fields[k] != candidate.fields[k]}
        self.assertEqual(changed, {'mode', 'status'})
        self.assertEqual((candidate.fields['mode'], candidate.fields['status']), ('LEARNING', 'ACTIVE'))
        self.assertEqual(self.store.read_context(DELIVERY), root)
        with self.assertRaises(ValueError):
            delivery.apply(DELIVERY, 'admin', proposal.ref, 'undecided')
        self.author.review_and_apply(DELIVERY, proposal, 'activate', service=delivery)
        root = self.store.read_context(DELIVERY)
        self.assertEqual((root.fields['mode'], root.fields['status']), ('LEARNING', 'ACTIVE'))
        self.assertEqual(delivery.propose_activation(DELIVERY, 'admin', base, request_id='activate'), result)
        with self.assertRaisesRegex(ValueError, 'PREPARATION DRAFT'):
            self.activation(delivery, request_id='reactivate')

    def test_learner_history_blocks_activation_at_proposal_and_application(self):
        release = self.released()
        with patch.dict('learning.releases.RUNTIME_WORKERS', SIMULATED_ASSESSOR):
            _, delivery = self.imported(release)
        proposal = self.store.read(self.activation(delivery).proposal, owner=DELIVERY)
        delivery.decide(DELIVERY, 'admin', proposal.ref, 'APPROVE', 'Synthetic activation review')
        self.seed_history(DELIVERY)
        with self.assertRaises(ActivationRefused) as refused:
            delivery.apply(DELIVERY, 'admin', proposal.ref, 'activate')
        self.assertEqual({f.code for f in refused.exception.findings}, {'RELEASE_LEARNER_HISTORY'})
        with self.assertRaises(ActivationRefused):
            self.activation(delivery, request_id='again')
        self.assertEqual(self.store.read_context(DELIVERY).fields['mode'], 'PREPARATION')


@on_both_backends
class ReservedRuleTest(ReleaseTest):
    def test_generic_proposals_cannot_create_releases_or_bypass_the_import(self):
        release = self.released()
        root = self.store.read_context(AUTH)
        manifest = ReleaseManifest.model_validate_json(release.fields['contentOrLocator'])
        copy = release.model_copy(update={'version': 'generic'})
        disguised = release.model_copy(update={'id': 'course:substituted-release'})
        catalogue_entry = next(r for r in root.fields['models'] if r['id'].startswith('authoring-release:'))
        stripped = entity('ExecutionContext', AUTH, {**root.fields,
            'models': [r for r in root.fields['models'] if r != catalogue_entry]}, 'stripped')
        for candidates in ((copy,), (disguised,), (stripped,)):
            with self.assertRaisesRegex(ValueError, 'dedicated commands'):
                self.service.propose(AUTH, 'admin', (root.ref,), candidates, 'Generic release attempt')
        # A direct proposal that skips the command is refused at application.
        context = self.service._context(AUTH, 'admin')
        bypass = create_proposal(context, (root.ref,), (disguised,), 'Direct release bypass')
        save_proposal(self.store, context, bypass, (disguised,))
        self.service.decide(AUTH, 'admin', bypass.ref, 'APPROVE', 'Synthetic review of a bypass')
        with self.assertRaisesRegex(ValueError, 'dedicated commands'):
            self.service.apply(AUTH, 'admin', bypass.ref, 'bypass')
        # The reference-fixture style generic import is no longer possible.
        with self.store.db:
            self.store.db.execute('BEGIN')
            _, definitions = released_entities(self.store, self.author.context(), release)
        destination = self.store.read_context(DELIVERY)
        imported = entity('ExecutionContext', DELIVERY, {**destination.fields, 'models': [manifest.domain.model_dump()],
                          'learningDesign': manifest.design.model_dump()}, 'generic-import')
        with self.assertRaisesRegex(ValueError, 'dedicated commands'):
            self.service.propose(DELIVERY, 'admin', (destination.ref,), (*definitions, imported), 'Generic import')
        context = self.service._context(DELIVERY, 'admin')
        bypass = create_proposal(context, (destination.ref,), (*definitions, imported), 'Direct import bypass')
        save_proposal(self.store, context, bypass, (*definitions, imported))
        self.service.decide(DELIVERY, 'admin', bypass.ref, 'APPROVE', 'Synthetic review of a bypass')
        with self.assertRaisesRegex(ValueError, 'dedicated commands'):
            self.service.apply(DELIVERY, 'admin', bypass.ref, 'bypass')
        self.assertEqual(self.store.read_context(DELIVERY), destination)
        self.assertEqual(self.store.read_context(AUTH), root)

    def test_import_refuses_applied_pins_that_differ_from_the_reviewed_project(self):
        release = self.released()
        manifest = ReleaseManifest.model_validate_json(release.fields['contentOrLocator'])
        forged = release.model_copy(update={'version': 'forged', 'fields': {**release.fields,
            'contentOrLocator': manifest.model_copy(update={'artifacts': manifest.artifacts[:-1]}).model_dump_json()}})
        # Simulate a legacy generic release applied before the reserved rules existed.
        with patch('learning.releases.refuse_generic'), patch('learning.releases.validate_release_application'):
            root = self.store.read_context(AUTH)
            self.author.review_and_apply(AUTH, self.service.propose(AUTH, 'admin', (root.ref,), (forged,),
                                         'Legacy generic release'), 'legacy')
        command = DeliveryImport(release=forged.ref, authoring_context=AUTH,
            base_context=self.store.read_context(DELIVERY).ref, scope_name='scope')
        with self.assertRaisesRegex(ValueError, 'pins do not match'):
            self.service.propose_delivery_import(DELIVERY, 'admin', command, request_id='forged')
        self.assertIn('RELEASE_PIN_MISMATCH', {f.code for f in self.service.inspect_release(AUTH, 'admin', forged.ref).findings})


@on_both_backends
class ReleaseCliTest(ReleaseTest):
    def test_cli_release_inspection_import_preview_and_activation_refusal(self):
        self.build()
        policy = Path(self.temp.name) / 'policy.json'
        policy.write_text(self.service.policy.model_dump_json())
        original = policy.read_bytes()
        def cli(context, *arguments, confirm=False, code=0):
            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors), \
                    patch('builtins.input', return_value='CONFIRM' if confirm else ''):
                self.assertEqual(main(['--db', str(self.path), '--policy', str(policy), '--subject', 'admin',
                                       '--context', context, *arguments]), code, errors.getvalue())
            return None if confirm or code else json.loads(output.getvalue()), errors.getvalue()
        with ExitStack() as stack:
            for factory in ('_orchestrator', '_aimpro_authoring', '_aimpro_search', '_aimpro_lead'):
                stack.enter_context(patch('learning.__main__.' + factory, side_effect=AssertionError('No external call')))
            result, _ = cli(AUTH, 'propose-release', '--project', self.author.project.ref.model_dump_json(),
                '--domain', self.author.domain.ref.model_dump_json(),
                '--base-context', self.store.read_context(AUTH).ref.model_dump_json(), '--request-id', 'cli-release')
            cli(AUTH, 'decide', json.dumps(result['proposal']), 'APPROVE', '--reason', 'Synthetic CLI review', confirm=True)
            cli(AUTH, 'apply', json.dumps(result['proposal']), '--operation-id', 'cli-release')
            view, _ = cli(AUTH, 'show-release', json.dumps(result['release']))
            self.assertFalse(view['findings'])
            self.assertEqual(view['receipt']['proposal']['id'], result['proposal']['id'])
            release = self.store.read(EntityRef.model_validate(result['release']), owner=AUTH)
            bundle = Path(self.temp.name) / 'import.json'
            bundle.write_text(DeliveryImport(release=release.ref, authoring_context=AUTH,
                base_context=self.store.read_context(DELIVERY).ref, scope_name='cli-scope',
                bindings=self.author.selections(release, 'cli-scope')).model_dump_json())
            existing = Path(self.temp.name) / 'existing.json'
            existing.write_text('{}')
            cli(DELIVERY, 'propose-delivery-import', str(bundle), '--request-id', 'cli-import',
                '--policy-preview', str(existing), code=2)
            preview = Path(self.temp.name) / 'preview.json'
            imported, _ = cli(DELIVERY, 'propose-delivery-import', str(bundle), '--request-id', 'cli-import',
                              '--policy-preview', str(preview))
            self.assertEqual(json.loads(preview.read_text()), imported['policy_preview'])
            self.assertEqual(policy.read_bytes(), original)
            self.assertEqual(existing.read_text(), '{}')
            cli(DELIVERY, 'decide', json.dumps(imported['proposal']), 'APPROVE', '--reason', 'Synthetic destination review', confirm=True)
            cli(DELIVERY, 'apply', json.dumps(imported['proposal']), '--operation-id', 'cli-import')
            base = self.store.read_context(DELIVERY).ref.model_dump_json()
            _, errors = cli(DELIVERY, 'propose-activation', '--base-context', base, '--request-id', 'cli-activate', code=2)
            self.assertIn('RELEASE_POLICY_NOT_INSTALLED', errors)
            policy = preview
            _, errors = cli(DELIVERY, 'propose-activation', '--base-context', base, '--request-id', 'cli-activate', code=2)
            self.assertIn('RELEASE_RUNTIME_ROLE', errors)
            self.assertIn('RELEASE_COMPLETION_HANDLER', errors)


if __name__ == '__main__':
    unittest.main()
