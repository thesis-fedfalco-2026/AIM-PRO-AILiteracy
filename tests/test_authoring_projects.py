"""Production project boundaries, replay and CLI; agents remain synthetic."""

from contextlib import ExitStack, redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from aimpro.audit import DEFAULT_PROJECT
from learning.__main__ import main
from learning.authoring import ArtifactSelection, ProjectManifest
from learning.contracts import EntityRef, make_entity
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.projects import ProjectInitialization, ProjectRevision, _curator_selection
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from tests.authoring_cycle_fixtures import AUTH, DELIVERY, SimulatedAuthoring, trusted_policy
from tests.syllabus_fixtures import Curator, Reviewer
from tests.test_aimpro_retrieval import response
from tests.store_backends import block_network, new_store_location, on_both_backends


@on_both_backends
class AuthoringProjectTest(unittest.TestCase):
    def setUp(self):
        block_network(self, 'Project acceptance must not use the network')
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = new_store_location(self, self.temp.name, 'project.sqlite')
        self.store = LearningStore(self.path)
        self.addCleanup(self.store.close)
        self.models = Mock(side_effect=AssertionError('Project operations must not construct models'))
        self.service = LearningService(self.store, load_contract(), trusted_policy(), self.models)
        self.root = self.service.bootstrap(AUTH, 'admin')
        self.service.bootstrap(DELIVERY, 'admin')
        self.author = SimulatedAuthoring(self.service)

    def syllabus(self, request_id='syllabus'):
        result = self.service.generate_aimpro_syllabus(AUTH, 'admin', DEFAULT_PROJECT,
            request_id=request_id, authoring_factory=lambda: (Curator(), Reviewer(), None),
            source_scope='wp3', query='prompting', k=3, search_factory=lambda: lambda *a, **kw: response())
        proposal = self.store.read(result.proposal_refs[0], owner=AUTH)
        resource = next(c for c in proposal_candidates(self.store, proposal) if c.id.endswith(':syllabus'))
        return proposal, resource

    def initialization(self, syllabus, project_id='test-project'):
        return ProjectInitialization(project_id=project_id, syllabus=syllabus.ref,
            base_context=self.store.read_context(AUTH).ref)

    def initialize(self, command, request_id='init'):
        return self.service.initialize_authoring_project(AUTH, 'admin', command, request_id=request_id)

    def apply(self, result, operation='apply-project'):
        proposal = self.store.read(result.proposal, owner=AUTH)
        return self.author.review_and_apply(AUTH, proposal, operation)

    def revision(self, version='1'):
        output, definitions, dependencies = self.author.assessment(version)
        selection = ArtifactSelection(key='assessment', kind='ASSESSMENT', resource=output.ref,
            definitions=tuple(d.ref for d in definitions), depends_on=dependencies)
        return ProjectRevision(project=self.author.project.ref,
            base_context=self.store.read_context(AUTH).ref, design=self.author.design.ref,
            artifacts=(selection,), candidates=(output, *definitions), explanation='Synthetic exact assessment selection')

    def revise(self, command, request_id='revise'):
        return self.service.revise_authoring_project(AUTH, 'admin', command, request_id=request_id)

    def test_initialization_requires_applied_approval_and_is_itself_reviewed(self):
        proposal, syllabus = self.syllabus()
        command = self.initialization(syllabus)
        for status in ('pending', 'rejected', 'approved'):
            if status != 'pending':
                self.service.decide(AUTH, 'admin', proposal.ref,
                    'REJECT' if status == 'rejected' else 'APPROVE', 'Synthetic explicit decision')
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.initialize(command)
            self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE id='init'").fetchone())
        self.service.apply(AUTH, 'admin', proposal.ref, 'syllabus')
        command = self.initialization(syllabus)
        before = self.store.read_context(AUTH)
        result = self.initialize(command)
        self.assertEqual(self.store.read_context(AUTH), before)
        with self.assertRaises(ValueError):
            self.service.inspect_authoring_project(AUTH, 'admin', 'test-project')
        with self.assertRaises(ValueError):
            self.service.approved_project_syllabus(AUTH, 'admin', result.project)
        self.apply(result)
        inspection = self.service.inspect_authoring_project(AUTH, 'admin', 'test-project')
        self.assertEqual(inspection.project, result.project)
        self.assertIsNotNone(inspection.receipt)
        self.assertTrue(all(a.receipt for a in inspection.artifacts))
        self.assertFalse(inspection.stale_dependencies)
        root = self.store.read_context(AUTH)
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        self.assertFalse(root.fields['learningStates'] or root.fields['resourceBindings'] or root.fields['activityOccurrences'])
        self.models.assert_not_called()

    def test_replay_after_application_is_exact_and_conflicting_requests_fail(self):
        proposal, syllabus = self.syllabus()
        self.author.review_and_apply(AUTH, proposal, 'syllabus')
        command = self.initialization(syllabus)
        result = self.initialize(command)
        self.apply(result)
        before = self.store.db.total_changes
        with patch('learning.projects._initialize', side_effect=AssertionError('Replay must not rebuild')):
            self.assertEqual(self.initialize(command), result)
        self.assertEqual(self.store.db.total_changes, before)
        with self.assertRaises(StateConflict):
            self.initialize(command.model_copy(update={'project_id': 'different'}))
        with self.assertRaises(StateConflict):
            self.initialize(self.initialization(syllabus), 'duplicate')
        self.store.claim_request('pending', AUTH, '{}')
        with self.assertRaises(StateConflict):
            self.initialize(command, 'pending')

    def test_concurrent_connections_share_one_completed_request(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        proposal, syllabus = self.syllabus()
        self.author.review_and_apply(AUTH, proposal, 'syllabus')
        command = self.initialization(syllabus)
        barrier = Barrier(2)
        def initialize_on_connection():
            with LearningStore(self.path) as store:
                service = LearningService(store, load_contract(), self.service.policy, self.models)
                barrier.wait(timeout=5)
                return service.initialize_authoring_project(AUTH, 'admin', command, request_id='concurrent')
        before = len(self.store.owned(AUTH, 'ChangeProposal'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(initialize_on_connection) for _ in range(2)]
            results = [f.result(timeout=10) for f in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.store.owned(AUTH, 'ChangeProposal')), before + 1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM requests WHERE id='concurrent'").fetchone()[0], 1)

    def test_atomic_proposal_failure_and_application_failure_leave_no_partial_state(self):
        proposal, syllabus = self.syllabus()
        self.author.review_and_apply(AUTH, proposal, 'syllabus')
        command = self.initialization(syllabus)
        count = self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0]
        with patch.object(self.store, 'finish_request', side_effect=RuntimeError('Injected persistence failure')):
            with self.assertRaises(RuntimeError):
                self.initialize(command)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0], count)
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE id='init'").fetchone())
        result = self.initialize(command)
        self.service.decide(AUTH, 'admin', result.proposal, 'APPROVE', 'Synthetic project review')
        root = self.store.read_context(AUTH)
        count = self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0]
        original = self.store._put
        def fail_on_domain(entity, *args, **kwargs):
            if entity.ref == result.domain:
                raise RuntimeError('Injected mid-application failure')
            return original(entity, *args, **kwargs)
        with patch.object(self.store, '_put', side_effect=fail_on_domain), self.assertRaises(RuntimeError):
            self.service.apply(AUTH, 'admin', result.proposal, 'apply')
        self.assertEqual(self.store.read_context(AUTH), root)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0], count)
        self.assertIsNone(self.store.operation_result('apply', AUTH))
        self.assertIsNotNone(self.service.apply(AUTH, 'admin', result.proposal, 'apply'))

    def test_authority_and_foreign_context_are_rejected_before_resolution(self):
        proposal, syllabus = self.syllabus()
        self.author.review_and_apply(AUTH, proposal, 'syllabus')
        command = self.initialization(syllabus)
        before = self.store.db.total_changes
        with patch('learning.projects.resolve_artifact', side_effect=AssertionError('Must authorize first')):
            with self.assertRaises(ValueError):
                self.service.initialize_authoring_project(AUTH, 'learner', command, request_id='unauthorized')
        self.assertEqual(self.store.db.total_changes, before)
        foreign = command.model_copy(update={'base_context': self.store.read_context(DELIVERY).ref})
        with self.assertRaises(ValueError):
            self.service.initialize_authoring_project(DELIVERY, 'admin', foreign, request_id='foreign')
        self.author.curator()
        for operation in (
            lambda: self.service.inspect_authoring_project(AUTH, 'learner', 'synthetic-course'),
            lambda: self.service.approved_project_syllabus(AUTH, 'learner', self.author.project.ref),
            lambda: self.service.inspect_authoring_project(DELIVERY, 'admin', 'synthetic-course')):
            with self.assertRaises(ValueError):
                operation()
        # A learner with a mistakenly added propose grant still lacks content authority.
        policy = self.service.policy.model_dump()
        policy['subjects']['learner']['actions'][AUTH] = ['read', 'propose']
        self.service.policy = type(self.service.policy).model_validate(policy)
        with self.assertRaises(ValueError):
            self.service.inspect_authoring_project(AUTH, 'learner', 'synthetic-course')

    def test_inspection_and_resolution_are_read_only_and_recheck_revoked_approvals(self):
        proposal = self.author.curator()
        before = self.store.db.total_changes
        view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        self.assertEqual(self.service.approved_project_syllabus(AUTH, 'admin', view.project), self.author.initial_receipt)
        self.assertEqual(self.store.db.total_changes, before)
        self.service.decide(AUTH, 'admin', proposal.ref, 'REJECT', 'Revoke synthetic syllabus approval')
        view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        self.assertIsNotNone(view.receipt)
        self.assertTrue(all(a.approval_error for a in view.artifacts))
        with self.assertRaises(ValueError):
            self.service.approved_project_syllabus(AUTH, 'admin', view.project)

    def test_application_rechecks_dependency_approval_without_context_change(self):
        syllabus_proposal = self.author.curator()
        result = self.revise(self.revision())
        self.service.decide(AUTH, 'admin', result.proposal, 'APPROVE', 'Synthetic exact project review')
        before = self.store.read_context(AUTH)
        self.service.decide(AUTH, 'admin', syllabus_proposal.ref, 'REJECT', 'Revoke an input approval')
        self.assertEqual(self.store.read_context(AUTH), before)
        with self.assertRaises(ValueError):
            self.service.apply(AUTH, 'admin', result.proposal, 'revoked-input')
        self.assertEqual(self.store.read_context(AUTH), before)
        with self.assertRaises(ValueError):
            self.store.read(result.project, owner=AUTH)
        self.assertIsNone(self.store.operation_result('revoked-input', AUTH))

    def test_stale_context_and_project_cannot_silently_rebase(self):
        self.author.curator()
        command = self.revision()
        first = self.revise(command)
        second = self.revise(command, 'competing')
        self.apply(first)
        with self.assertRaises(StateConflict):
            self.revise(command, 'stale-context')
        fresh_context = command.model_copy(update={'base_context': self.store.read_context(AUTH).ref})
        with self.assertRaises(StateConflict):
            self.revise(fresh_context, 'stale-project')
        self.service.decide(AUTH, 'admin', second.proposal, 'APPROVE', 'Synthetic competing review')
        with self.assertRaises(StateConflict):
            self.service.apply(AUTH, 'admin', second.proposal, 'competing')
        self.assertEqual(self.revise(command), first)

    def test_new_dependency_versions_must_be_selected_and_lineage_must_match(self):
        self.author.curator()
        command = self.revision()
        selection = command.artifacts[0]
        unavailable = EntityRef(type='Resource', id='not-selected', version='1')
        for bad in (
            selection.model_copy(update={'depends_on': (unavailable,)}),
            selection.model_copy(update={'depends_on': (selection.resource,)}),
            selection.model_copy(update={'depends_on': ()}),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.revise(command.model_copy(update={'artifacts': (bad,)}))
        # Explicit lineage cannot make an unavailable dependency selected.
        output = command.candidates[0]
        output = output.model_copy(update={'fields': {**output.fields,
            'derivedFrom': [*output.fields['derivedFrom'], unavailable.model_dump()]}})
        bad = selection.model_copy(update={'depends_on': (*selection.depends_on, unavailable)})
        with self.assertRaises(StateConflict):
            self.revise(command.model_copy(update={'artifacts': (bad,), 'candidates': (output, *command.candidates[1:])}))
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE id='revise'").fetchone())

    def test_revision_rejects_execution_state_unrelated_candidates_and_definition_changes(self):
        self.author.curator()
        command = self.revision()
        root = self.store.read_context(AUTH)
        for extra in (
            root.model_copy(update={'version': 'illegal-state'}),
            make_entity('Topic', 'unrelated', {'name': 'Unrelated', 'definition': 'Outside project closure'}),
            self.author.topic.model_copy(update={'fields': {**self.author.topic.fields, 'name': 'Overwritten'}}),
        ):
            with self.subTest(extra=extra.type), self.assertRaises(ValueError):
                self.revise(command.model_copy(update={'candidates': (*command.candidates, extra)}))
        duplicate = command.model_copy(update={'artifacts': (command.artifacts[0], command.artifacts[0])})
        with self.assertRaises(ValueError):
            self.revise(duplicate)
        self.assertEqual(self.store.read_context(AUTH), root)

    def test_generic_proposals_cannot_bypass_project_application_contract(self):
        self.author.curator()
        result = self.revise(self.revision())
        saved = proposal_candidates(self.store, self.store.read(result.proposal, owner=AUTH))
        project = next(c for c in saved if c.ref == result.project)
        manifest = ProjectManifest.model_validate_json(project.fields['contentOrLocator'])
        forged = manifest.model_copy(update={'required_kinds': ('SOURCE', 'SYLLABUS')})
        project = project.model_copy(update={'fields': {**project.fields, 'contentOrLocator': forged.model_dump_json()}})
        proposal = self.service.propose(AUTH, 'admin', (self.store.read_context(AUTH).ref,),
            tuple(project if c.ref == project.ref else c for c in saved), 'Synthetic bypass attempt')
        self.service.decide(AUTH, 'admin', proposal.ref, 'APPROVE', 'Synthetic generic resource review')
        before = self.store.read_context(AUTH)
        with self.assertRaises(ValueError):
            self.service.apply(AUTH, 'admin', proposal.ref, 'bypass')
        self.assertEqual(self.store.read_context(AUTH), before)

    def test_catalogue_only_changes_cannot_roll_back_or_remove_a_project(self):
        self.author.curator()
        root = self.store.read_context(AUTH)
        stripped = root.model_copy(update={'version': 'remove-project', 'fields': {
            **root.fields, 'models': [m for m in root.fields['models'] if m['id'] != self.author.domain.id]}})
        proposal = self.service.propose(AUTH, 'admin', (root.ref,), (stripped,), 'Synthetic catalogue removal')
        self.service.decide(AUTH, 'admin', proposal.ref, 'APPROVE', 'Synthetic generic review')
        with self.assertRaisesRegex(ValueError, 'catalogue'):
            self.service.apply(AUTH, 'admin', proposal.ref, 'remove-project')
        self.assertEqual(self.store.read_context(AUTH), root)

    def test_decision_changed_between_validation_and_write_is_rejected(self):
        self.author.curator()
        result = self.revise(self.revision())
        self.service.decide(AUTH, 'admin', result.proposal, 'APPROVE', 'Synthetic exact review')
        original = self.store.commit_change
        def revoke_before_lock(*args, **kwargs):
            self.service.decide(AUTH, 'admin', result.proposal, 'REJECT', 'Concurrent revocation')
            return original(*args, **kwargs)
        before = self.store.read_context(AUTH)
        with patch.object(self.store, 'commit_change', side_effect=revoke_before_lock):
            with self.assertRaisesRegex(StateConflict, 'decision changed'):
                self.service.apply(AUTH, 'admin', result.proposal, 'revoked-during-apply')
        self.assertEqual(self.store.read_context(AUTH), before)
        self.assertIsNone(self.store.operation_result('revoked-during-apply', AUTH))

    def test_explicit_new_approved_curator_selection_marks_old_dependants_stale(self):
        self.author.curator()
        assessment = self.revise(self.revision())
        self.apply(assessment)
        old_syllabus = self.author.initial_receipt
        proposal, syllabus = self.syllabus('new-curator')
        self.author.review_and_apply(AUTH, proposal, 'new-curator')
        # Composite/current design evolution cannot invalidate the explicit old selection.
        self.assertEqual(self.service.approved_project_syllabus(AUTH, 'admin', assessment.project), old_syllabus)
        with self.store.db:
            self.store.db.execute('BEGIN')
            _, selections, design = _curator_selection(self.store, self.service._context(AUTH, 'admin'), syllabus.ref)
        command = ProjectRevision(project=assessment.project, base_context=self.store.read_context(AUTH).ref,
            design=design, artifacts=selections, explanation='Explicit rebase to another approved Curator syllabus')
        result = self.revise(command, 'new-input')
        self.apply(result, 'new-input')
        view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        self.assertEqual({f.target for f in view.stale_dependencies}, {'assessment'})
        self.assertTrue(all(a.receipt for a in view.artifacts))
        self.assertEqual(self.service.approved_project_syllabus(AUTH, 'admin', result.project).syllabus, syllabus.ref)
        self.assertEqual(self.store.read(assessment.project, owner=AUTH).ref, assessment.project)

    def test_cli_initialization_revision_inspection_resolution_and_review(self):
        proposal, syllabus = self.syllabus()
        self.author.review_and_apply(AUTH, proposal, 'syllabus')
        policy = Path(self.temp.name) / 'policy.json'
        policy.write_text(self.service.policy.model_dump_json())
        args = ['--db', str(self.path), '--policy', str(policy), '--subject', 'admin', '--context', AUTH]
        def cli(*arguments, confirm=False):
            output = StringIO()
            with redirect_stdout(output), patch('builtins.input', return_value='CONFIRM' if confirm else ''):
                self.assertEqual(main([*args, *arguments]), 0)
            # decide prints the reviewed payload before its result.
            return None if confirm else json.loads(output.getvalue())
        with ExitStack() as stack:
            for factory in ('_orchestrator', '_aimpro_authoring', '_aimpro_search', '_aimpro_lead'):
                stack.enter_context(patch('learning.__main__.' + factory, side_effect=AssertionError('No external call')))
            result = cli('init-authoring-project', 'cli-project', '--syllabus', syllabus.ref.model_dump_json(),
                '--base-context', self.store.read_context(AUTH).ref.model_dump_json(), '--request-id', 'cli-init')
            cli('decide', json.dumps(result['proposal']), 'APPROVE', '--reason', 'Explicit synthetic CLI review', confirm=True)
            cli('apply', json.dumps(result['proposal']), '--operation-id', 'cli-apply')
            view = cli('show-authoring-project', 'cli-project')
            approved = cli('show-project-syllabus', json.dumps(view['project']))
            self.assertEqual(approved['syllabus'], syllabus.ref.model_dump())
            # Reuse simulated assessment generation, but persist this revision through the real CLI.
            self.author.project = self.store.read(EntityRef.model_validate(view['project']), owner=AUTH)
            self.author.design = self.store.read(EntityRef.model_validate(view['manifest']['design']), owner=AUTH)
            saved = proposal_candidates(self.store, proposal)
            self.author.syllabus = syllabus
            self.author.outcome = next(c for c in saved if c.type == 'LearningOutcome')
            self.author.topic = next(c for c in saved if c.type == 'Topic')
            bundle = Path(self.temp.name) / 'revision.json'
            bundle.write_text(self.revision().model_dump_json())
            revision = cli('revise-authoring-project', str(bundle), '--request-id', 'cli-revise')
            self.assertEqual(cli('revise-authoring-project', str(bundle), '--request-id', 'cli-revise'), revision)
            cli('decide', json.dumps(revision['proposal']), 'APPROVE', '--reason', 'Explicit synthetic revision review', confirm=True)
            cli('apply', json.dumps(revision['proposal']), '--operation-id', 'cli-revision')
            view = cli('show-authoring-project', 'cli-project')
            self.assertEqual(view['project'], revision['project'])
            self.assertEqual(len(view['artifacts']), 3)
            self.assertTrue(all(a['receipt'] for a in view['artifacts']))
            bundle.write_text('null')
            with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
                self.assertEqual(main([*args, 'revise-authoring-project', str(bundle), '--request-id', 'bad']), 2)
