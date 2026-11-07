"""Production authoring orchestration with synthetic typed model responses."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from aimpro.generation_state import GeneratedArtifact
from aimpro.generators import (AssessmentStimulus, GenerationCommand, GenerationInput,
                               StimulusRequirement, generate)
from learning.__main__ import main
from learning.authoring import ProjectManifest
from learning.contracts import EntityRef
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from tests.authoring_cycle_fixtures import AUTH, SimulatedAuthoring, trusted_policy
from tests.generator_fixtures import SyntheticModels


class AuthoringGeneratorTest(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(target, side_effect=AssertionError('Generator tests must not use the network'))
            blocked = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(blocked.assert_not_called)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'generators.sqlite'
        self.store = LearningStore(self.path)
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), trusted_policy(), Mock())
        self.service.bootstrap(AUTH, 'admin')
        self.author = SimulatedAuthoring(self.service)
        self.syllabus_proposal = self.author.curator()
        self.project = self.author.project.ref
        self.models = SyntheticModels()
        self.factory = Mock(side_effect=self.models.factory)

    def command(self, role='ASSESSMENT', **kwargs):
        view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        values = {'project': view.project, 'base_context': self.store.read_context(AUTH).ref}
        if role != 'ASSESSMENT':
            values['assessments'] = tuple(a.resource for a in view.manifest.artifacts if a.kind == 'ASSESSMENT')
        values.update(kwargs)
        return GenerationCommand(**values)

    def run_generator(self, role='ASSESSMENT', command=None, request_id='assessment', subject='admin'):
        method = {'ASSESSMENT': self.service.generate_project_assessments,
                  'TEACHER_CONTENT': self.service.generate_project_teacher,
                  'TRAINER_CONTENT': self.service.generate_project_trainer}[role]
        return method(AUTH, subject, command or self.command(role), request_id=request_id, authoring_factory=self.factory)

    def accept(self, result, operation='apply-output'):
        self.assertEqual(result.kind, 'PROPOSAL')
        proposal = self.store.read(result.proposal_refs[0], owner=AUTH)
        saved = proposal_candidates(self.store, proposal)
        self.author.review_and_apply(AUTH, proposal, operation)
        return saved

    def assessment(self):
        return self.accept(self.run_generator())

    def stimulus_command(self):
        command = self.command()
        syllabus = self.service.approved_project_syllabus(AUTH, 'admin', command.project)
        return command.model_copy(update={'stimulus_requirements': (StimulusRequirement(
            unit_key=syllabus.artifact.units[0].key, key='comparison', kind='PROMPT_VARIANT',
            brief='Supply the complete fictional prompt comparison text.'),)})

    def add_stimulus(self, data, draft):
        item = draft.units[0].items[0]
        stimulus = AssessmentStimulus(key='comparison', kind='PROMPT_VARIANT', title='Fictional comparison',
            content='Weak: Write a reminder. Improved: Write a polite reminder to fictional customer Alex about invoice EXAMPLE-01.',
            citations=item.citations)
        return replace_item(draft, item.model_copy(update={'stimuli': (stimulus,)}))

    def test_required_stimulus_is_in_reviewed_package_and_mapped_activity(self):
        command = self.stimulus_command()
        self.models.transform = self.add_stimulus
        result = self.run_generator(command=command)
        self.assertEqual(result.kind, 'PROPOSAL')
        saved = proposal_candidates(self.store, self.store.read(result.proposal_refs[0], owner=AUTH))
        package = GeneratedArtifact.model_validate_json(next(e for e in saved if e.type == 'Resource'
            and e.id.startswith('authoring-output:')).fields['contentOrLocator'])
        stimulus = package.draft.units[0].items[0].stimuli[0]
        self.assertEqual(package.inputs.command.stimulus_requirements, command.stimulus_requirements)
        self.assertTrue(any(stimulus.content in e.fields['instruction'] for e in saved if e.type == 'ActivityDefinition'))
        self.assertEqual(self.models.calls, ['assessment-designer', 'LEAD_REVIEW'])
        # The new declaration remains part of the exact replay identity.
        self.assertEqual(self.run_generator(command=command), result)
        with self.assertRaises(StateConflict):
            self.run_generator(command=command.model_copy(update={'stimulus_requirements': ()}))

    def test_missing_invalid_or_uncited_stimuli_fail_before_lead(self):
        command = self.stimulus_command()
        before = self.store.owned(AUTH, 'ChangeProposal')
        for case in ('missing', 'blank', 'duplicate', 'wrong-kind', 'foreign-citation'):
            def transform(data, draft):
                if case == 'missing':
                    return draft
                draft = self.add_stimulus(data, draft)
                item = draft.units[0].items[0]
                stimulus = item.stimuli[0]
                if case == 'blank':
                    stimulus = stimulus.model_copy(update={'content': '   '})
                elif case == 'wrong-kind':
                    stimulus = stimulus.model_copy(update={'kind': 'TRANSCRIPT'})
                elif case == 'foreign-citation':
                    stimulus = stimulus.model_copy(update={'citations': (stimulus.citations[0].model_copy(
                        update={'resource_version': 'not-supplied'}),)})
                stimuli = (stimulus, stimulus) if case == 'duplicate' else (stimulus,)
                return replace_item(draft, item.model_copy(update={'stimuli': stimuli}))
            self.models.transform = transform
            self.models.calls.clear()
            with self.subTest(case=case):
                self.assertEqual(self.run_generator(command=command, request_id='stimulus-' + case).kind, 'FAILURE')
                self.assertEqual(self.models.calls, ['assessment-designer'])
        self.assertEqual(self.store.owned(AUTH, 'ChangeProposal'), before)

    def test_unknown_stimulus_unit_fails_before_reservation_or_models(self):
        command = self.stimulus_command()
        unknown = command.stimulus_requirements[0].model_copy(update={'unit_key': 'foreign-unit'})
        with self.assertRaisesRegex(ValueError, 'unknown approved syllabus unit'):
            self.run_generator(command=command.model_copy(update={'stimulus_requirements': (unknown,)}))
        self.factory.assert_not_called()
        self.assertIsNone(self.store.db.execute("SELECT 1 FROM requests WHERE id='assessment'").fetchone())

    def test_legacy_command_serialization_keeps_original_request_shape(self):
        command = self.command()
        expected = {'project': command.project.model_dump(), 'base_context': command.base_context.model_dump(),
                    'assessments': [], 'shared_content': [], 'requirements': []}
        self.assertEqual(command.model_dump(mode='json'), expected)
        self.assertEqual(json.loads(command.model_dump_json()), expected)
        self.assertIn('stimulus_requirements', self.stimulus_command().model_dump(mode='json'))

    def test_duplicate_stimulus_plan_keys_are_rejected(self):
        command = self.stimulus_command().model_dump(mode='json')
        command['stimulus_requirements'] *= 2
        with self.assertRaisesRegex(ValueError, 'Stimulus requirement keys must be unique'):
            GenerationCommand.model_validate(command)

    def test_evaluator_dispatch_concrete_rubrics_exact_lineage_and_pending_lifecycle(self):
        command = self.command()
        before = self.store.read_context(AUTH)
        result = self.run_generator(command=command)
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(self.store.read_context(AUTH), before)
        proposal = self.store.read(result.proposal_refs[0], owner=AUTH)
        saved = proposal_candidates(self.store, proposal)
        package_resource = next(e for e in saved if e.type == 'Resource' and e.id.startswith('authoring-output:'))
        package = GeneratedArtifact.model_validate_json(package_resource.fields['contentOrLocator'])
        self.assertEqual(package.inputs.command, command)
        self.assertEqual(self.models.calls, ['assessment-designer', 'LEAD_REVIEW'])
        self.assertIn('CATEGORY evaluator', self.models.agent_configs[0]['backstory'])
        self.assertEqual(self.models.agent_configs[0]['tools'], [])
        self.assertFalse(self.models.agent_configs[0]['allow_delegation'])
        self.assertEqual(self.models.llms.call_args.args[1].temperature, .1)
        activity = next(e for e in saved if e.type == 'ActivityDefinition')
        spec = next(e for e in saved if e.type == 'AssessmentSpecification')
        rubric = next(e for e in saved if e.type == 'Rubric')
        self.assertEqual(activity.fields['intent'], 'ASSESS')
        self.assertEqual(spec.fields['activities'], [activity.ref.model_dump()])
        self.assertEqual(spec.fields['rubric'], rubric.ref.model_dump())
        self.assertNotIn('decisionRule', spec.fields)
        self.assertNotIn('aggregationRule', rubric.fields)
        self.assertIn(self.models.inputs[0].constraints[0], activity.fields['instruction'])
        manifest = ProjectManifest.model_validate_json(next(e for e in saved if e.id == command.project.id).fields['contentOrLocator'])
        selection = next(a for a in manifest.artifacts if a.kind == 'ASSESSMENT')
        self.assertEqual(selection.depends_on, self.models.inputs[0].dependencies)
        self.assertEqual(package_resource.fields['derivedFrom'], [r.model_dump() for r in selection.depends_on])
        row = self.store.db.execute("SELECT payload FROM requests WHERE id='assessment'").fetchone()
        self.assertEqual(json.loads(row[0])['input_snapshot'], package.inputs.model_dump(mode='json'))
        with self.assertRaises(ValueError):
            self.service.apply(AUTH, 'admin', proposal.ref, 'unreviewed')
        self.accept(result)
        self.assertEqual(self.service.approved_project_syllabus(AUTH, 'admin', selection_project(self.service)).syllabus,
                         self.author.syllabus.ref)
        root = self.store.read_context(AUTH)
        self.assertEqual((root.fields['mode'], root.fields['status']), ('PREPARATION', 'DRAFT'))
        self.assertFalse(root.fields['resourceBindings'] or root.fields['activityOccurrences'] or root.fields['learningStates'])

    def test_authorization_precedes_resolution_factories_and_reservation(self):
        command = self.command()
        policy = self.service.policy.model_dump()
        policy['subjects']['learner']['actions'][AUTH] = ['read', 'propose']
        self.service.policy = type(self.service.policy).model_validate(policy)
        # Record the learner as a participant without granting content authority.
        from learning.contracts import make_entity
        root = self.store.read_context(AUTH)
        learner = make_entity('Participant', 'authoring-learner', {'subjectKey': 'learner', 'roles': ['LEARNER']})
        updated = root.model_copy(update={'version': 'with-learner', 'fields': {
            **root.fields, 'participants': [*root.fields['participants'], learner.ref.model_dump()]}})
        proposal = self.service.propose(AUTH, 'admin', (root.ref,), (learner, updated), 'Explicit synthetic learner enrollment')
        self.author.review_and_apply(AUTH, proposal, 'enroll')
        before = self.store.db.total_changes
        with patch('learning.generation.resolve_inputs', side_effect=AssertionError('Must authorize first')):
            for role in ('ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'):
                with self.subTest(role=role), self.assertRaises(ValueError):
                    self.run_generator(role, command, subject='learner')
        self.factory.assert_not_called()
        self.assertEqual(self.store.db.total_changes, before)

    def test_rejection_uncertainty_false_flags_and_wrong_review_type_leave_no_proposal(self):
        before = self.store.owned(AUTH, 'ChangeProposal')
        for i, fields in enumerate(({'verdict': 'REJECT'}, {'verdict': 'UNCERTAIN'},
            {'source_alignment': False}, {'citation_support': False},
            {'intent_correct': False}, {'content_complete': False})):
            original = self.models.verdict
            self.models.verdict = original.model_copy(update=fields)
            self.assertEqual(self.run_generator(request_id='review-' + str(i)).kind, 'FAILURE')
            self.models.verdict = original
        self.models.verdict = self.author.initial_receipt.artifact.review
        self.assertEqual(self.run_generator(request_id='wrong-review').kind, 'FAILURE')
        self.assertEqual(self.store.owned(AUTH, 'ChangeProposal'), before)

    def test_invalid_assessment_outputs_fail_before_lead_review(self):
        def mutate(data, draft):
            item = draft.units[0].items[0]
            criterion = item.criteria[0]
            level = criterion.levels[0]
            cases = [
                draft.model_copy(update={'input_digest': 'invented'}),
                draft.model_copy(update={'units': draft.units * 2}),
                replace_item(draft, item.model_copy(update={'outcomes': (EntityRef(type='LearningOutcome', id='future', version='1'),)})),
                replace_item(draft, item.model_copy(update={'criteria': item.criteria * 2})),
                replace_item(draft, item.model_copy(update={'criteria': (criterion.model_copy(update={'levels': (level, level)}),)})),
                replace_item(draft, item.model_copy(update={'criteria': (criterion.model_copy(update={'levels': (level.model_copy(update={'descriptor': 'Emerging'}), criterion.levels[1])}),)})),
                replace_item(draft, item.model_copy(update={'citations': (item.citations[0].model_copy(update={'resource_version': 'wrong'}),)})),
                replace_item(draft, item.model_copy(update={'citations': (item.citations[0].model_copy(update={'document_ids': ('future',)}),)})),
                replace_item(draft, item.model_copy(update={'intent': 'EXPLAIN'})),
            ]
            return cases[self.case]
        self.models.transform = mutate
        for self.case in range(9):
            self.models.calls.clear()
            with self.subTest(case=self.case):
                self.assertEqual(self.run_generator(request_id='invalid-' + str(self.case)).kind, 'FAILURE')
                self.assertEqual(self.models.calls, ['assessment-designer'])

    def test_completed_replay_after_application_is_exact_and_conflicting_reuse_fails(self):
        command = self.command()
        result = self.run_generator(command=command)
        self.accept(result)
        self.factory.reset_mock()
        self.factory.side_effect = AssertionError('Replay must not construct models')
        before = self.store.db.total_changes
        self.assertEqual(self.run_generator(command=command), result)
        self.assertEqual(self.store.db.total_changes, before)
        for changed in (command.model_copy(update={'requirements': ('New explicit requirement',)}), self.command()):
            with self.assertRaises(StateConflict):
                self.run_generator(command=changed)
        self.factory.assert_not_called()

    def test_snapshot_reserved_before_model_and_no_write_lock_during_external_work(self):
        def callback(data):
            self.assertFalse(self.store.db.in_transaction)
            with LearningStore(self.path) as other:
                row = other.db.execute("SELECT payload,result FROM requests WHERE id='assessment'").fetchone()
                self.assertIsNone(row['result'])
                self.assertEqual(json.loads(row['payload'])['input_snapshot'], data.model_dump(mode='json'))
                with other.db:
                    other.db.execute('BEGIN IMMEDIATE')
                    other.db.execute('INSERT INTO requests VALUES (?,?,?,NULL)', ('other-writer', AUTH, '{}'))
            with self.assertRaises(StateConflict):
                self.run_generator(command=data.command)
        self.models.callback = callback
        self.assertEqual(self.run_generator().kind, 'PROPOSAL')

    def test_context_change_and_project_revocation_during_model_work_are_rejected(self):
        for change in ('context', 'project'):
            with self.subTest(change=change):
                before = len(self.store.owned(AUTH, 'ChangeProposal'))
                def callback(data):
                    if change == 'context':
                        root = self.store.read_context(AUTH)
                        candidate = root.model_copy(update={'version': 'concurrent', 'fields': {**root.fields, 'status': 'PAUSED'}})
                        proposal = self.service.propose(AUTH, 'admin', (root.ref,), (candidate,), 'Synthetic concurrent change')
                        self.author.review_and_apply(AUTH, proposal, 'concurrent')
                    else:
                        self.service.decide(AUTH, 'admin', data.project_receipt.proposal, 'REJECT', 'Synthetic concurrent revocation')
                self.models.callback = callback
                result = self.run_generator(request_id='concurrent-' + change)
                self.assertEqual(result.kind, 'FAILURE')
                self.assertEqual(len(self.store.owned(AUTH, 'ChangeProposal')), before + (change == 'context'))
            # Restore draft status before checking the independent project revocation.
            if change == 'context':
                root = self.store.read_context(AUTH)
                updated = root.model_copy(update={'version': 'resume', 'fields': {**root.fields, 'status': 'DRAFT'}})
                proposal = self.service.propose(AUTH, 'admin', (root.ref,), (updated,), 'Synthetic return to draft')
                self.author.review_and_apply(AUTH, proposal, 'resume')

    def test_syllabus_revocation_during_model_work_is_rejected_without_context_change(self):
        before = self.store.read_context(AUTH)
        self.models.callback = lambda data: self.service.decide(AUTH, 'admin',
            self.syllabus_proposal.ref, 'REJECT', 'Revoke the exact Curator input')
        self.assertEqual(self.run_generator().kind, 'FAILURE')
        self.assertEqual(self.store.read_context(AUTH), before)

    def test_atomic_failure_rolls_back_candidates_and_pending_result_then_records_failure(self):
        original = self.store._put
        before = self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0]
        def fail(entity, *args, **kwargs):
            if entity.type == 'DomainModel':
                raise RuntimeError('Injected partial persistence failure')
            return original(entity, *args, **kwargs)
        with patch.object(self.store, '_put', side_effect=fail):
            result = self.run_generator()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0], before)
        row = self.store.db.execute("SELECT result FROM requests WHERE id='assessment'").fetchone()
        self.assertEqual(json.loads(row[0]), result.model_dump(mode='json'))

    def test_administrative_abandonment_during_generation_cannot_persist_proposal(self):
        before = self.store.owned(AUTH, 'ChangeProposal')
        self.models.callback = lambda data: self.service.abandon_request(AUTH, 'admin', 'assessment')
        result = self.run_generator()
        self.assertEqual(result.kind, 'FAILURE')
        self.assertIn('abandoned', result.content)
        self.assertEqual(self.store.owned(AUTH, 'ChangeProposal'), before)

    def test_teacher_and_trainer_dispatch_complete_assets_assessments_and_shared_materials(self):
        self.assessment()
        assessment_command = self.command('TEACHER_CONTENT')
        for role, name in (('TEACHER_CONTENT', 'teaching-designer'), ('TRAINER_CONTENT', 'practice-designer')):
            command = self.command(role)
            if role == 'TRAINER_CONTENT':
                view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
                teacher = next(a for a in view.manifest.artifacts if a.kind == 'TEACHER_CONTENT')
                command = command.model_copy(update={'shared_content': (teacher.resource,)})
                def share(data, draft):
                    shared = next(e.ref for a in data.inputs if a.selection.kind == 'TEACHER_CONTENT'
                                  for e in a.definitions if e.type == 'Resource')
                    return replace_item(draft, draft.units[0].items[0].model_copy(update={'shared_materials': (shared,)}))
                self.models.transform = share
            saved = self.accept(self.run_generator(role, command, request_id=role), operation=role)
            self.assertEqual(self.models.calls[-2:], [name, 'LEAD_REVIEW'])
            self.assertEqual(self.models.llms.call_args.args[1].temperature, .6 if role == 'TEACHER_CONTENT' else .4)
            package = next(GeneratedArtifact.model_validate_json(e.fields['contentOrLocator']) for e in saved
                           if e.type == 'Resource' and e.id.startswith('authoring-output:') and ':' not in e.id[len('authoring-output:'):])
            self.assertEqual(package.inputs.command.assessments, assessment_command.assessments)
            self.assertTrue(package.draft.materials)
            self.assertTrue(all(m.content for m in package.draft.materials))
            self.assertEqual(package.inputs.syllabus.syllabus, self.author.syllabus.ref)
            self.assertEqual(package.inputs.dependencies, (self.author.syllabus.ref, *command.assessments, *command.shared_content))
        self.assertEqual(self.store.read_context(AUTH).fields['mode'], 'PREPARATION')

    def test_trainer_review_scopes_accepted_limitations_gaps_and_shared_materials(self):
        self.assessment()
        lead, prefixes = self.models.review, {}
        def review(prompt, response_format):
            prefixes[self.models.calls[-1]] = prompt.split('\nDATA\n')[0]
            return lead(prompt, response_format)
        self.models.review = review
        for role in ('TEACHER_CONTENT', 'TRAINER_CONTENT'):
            self.accept(self.run_generator(role, request_id=role), operation=role)
        trainer = prefixes['practice-designer']
        # Accepted input limitations are out of the Trainer's scope; empty gaps is valid.
        self.assertTrue(trainer.startswith('TRAINER_REVIEW_SCOPE: '))
        self.assertIn('by themselves they never make it incomplete or misaligned', trainer)
        self.assertIn('empty gaps is valid when no new issue exists', trainer)
        self.assertIn('without command shared_content it is always empty', trainer)
        self.assertIn('must not reuse approved assessment prompt bodies', trainer)
        # The legacy Teacher route keeps the unchanged generic review prompt.
        self.assertTrue(prefixes['teaching-designer'].startswith('PROJECT_AUTHORING_REVIEW: '))

    def test_content_rejects_unapproved_missing_stale_and_foreign_assessments_before_models(self):
        for role in ('TEACHER_CONTENT', 'TRAINER_CONTENT'):
            with self.assertRaises(ValueError):
                self.run_generator(role, request_id=role)
        result = self.run_generator()
        pending = next(e.ref for e in proposal_candidates(self.store, self.store.read(result.proposal_refs[0], owner=AUTH))
                       if e.type == 'Resource' and e.id.startswith('authoring-output:'))
        for refs in ((pending,), (EntityRef(type='Resource', id='foreign', version='1'),)):
            with self.assertRaises(ValueError):
                self.run_generator('TEACHER_CONTENT', self.command('TEACHER_CONTENT', assessments=refs), request_id='invalid-input')
        self.factory.assert_called_once()

    def test_content_missing_assets_shared_references_and_intent_are_rejected(self):
        self.assessment()
        for role in ('TEACHER_CONTENT', 'TRAINER_CONTENT'):
            for case in ('missing', 'duplicate', 'shared', 'intent', 'citation'):
                def transform(data, draft):
                    item = draft.units[0].items[0]
                    changes = {
                        'missing': {'material_keys': ('not-produced',)},
                        'duplicate': {'material_keys': item.material_keys * 2},
                        'shared': {'shared_materials': (EntityRef(type='Resource', id='unapproved', version='1'),)},
                        'intent': {'intent': 'ASSESS'},
                        'citation': {'citations': (item.citations[0].model_copy(update={'resource_version': 'wrong'}),)},
                    }
                    return replace_item(draft, item.model_copy(update=changes[case]))
                self.models.transform = transform
                with self.subTest(role=role, case=case):
                    self.assertEqual(self.run_generator(role, request_id=role + case).kind, 'FAILURE')
                    self.assertNotEqual(self.models.calls[-1], 'LEAD_REVIEW')

    def test_content_rejection_uncertainty_replay_and_rollback(self):
        self.assessment()
        for role in ('TEACHER_CONTENT', 'TRAINER_CONTENT'):
            for verdict in ('REJECT', 'UNCERTAIN'):
                original = self.models.verdict
                self.models.verdict = original.model_copy(update={'verdict': verdict})
                before = len(self.store.owned(AUTH, 'ChangeProposal'))
                self.assertEqual(self.run_generator(role, request_id=role + verdict).kind, 'FAILURE')
                self.assertEqual(len(self.store.owned(AUTH, 'ChangeProposal')), before)
                self.models.verdict = original
            command = self.command(role)
            result = self.run_generator(role, command, request_id=role)
            self.accept(result, role)
            before = len(self.models.calls)
            self.assertEqual(self.run_generator(role, command, request_id=role), result)
            self.assertEqual(len(self.models.calls), before)
            original = self.store._put
            count = self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0]
            def fail(entity, *args, **kwargs):
                if entity.type == 'DomainModel':
                    raise RuntimeError('Injected content persistence failure')
                return original(entity, *args, **kwargs)
            with patch.object(self.store, '_put', side_effect=fail):
                self.assertEqual(self.run_generator(role, request_id=role + '-rollback').kind, 'FAILURE')
            self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0], count)

    def test_shared_teacher_revision_requires_focused_trainer_regeneration(self):
        self.assessment()
        self.accept(self.run_generator('TEACHER_CONTENT', request_id='teacher-1'), 'teacher-1')
        view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        old_teacher = next(a.resource for a in view.manifest.artifacts if a.kind == 'TEACHER_CONTENT')
        command = self.command('TRAINER_CONTENT', shared_content=(old_teacher,))
        self.accept(self.run_generator('TRAINER_CONTENT', command, request_id='trainer-1'), 'trainer-1')
        before = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        self.accept(self.run_generator('TEACHER_CONTENT', request_id='teacher-2'), 'teacher-2')
        after = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        self.assertEqual({f.target for f in after.stale_dependencies}, {'trainer_content'})
        unchanged = {a.kind: a.resource for a in before.manifest.artifacts if a.kind != 'TEACHER_CONTENT'}
        self.assertEqual({a.kind: a.resource for a in after.manifest.artifacts if a.kind != 'TEACHER_CONTENT'}, unchanged)
        with self.assertRaises(ValueError):
            self.run_generator('TRAINER_CONTENT', self.command('TRAINER_CONTENT', shared_content=(old_teacher,)), request_id='stale-shared')
        teacher = next(a.resource for a in after.manifest.artifacts if a.kind == 'TEACHER_CONTENT')
        command = self.command('TRAINER_CONTENT', shared_content=(teacher,))
        self.accept(self.run_generator('TRAINER_CONTENT', command, request_id='trainer-2'), 'trainer-2')
        self.assertFalse(self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course').stale_dependencies)

    def test_result_persistence_failure_rolls_back_the_entire_accepted_proposal(self):
        original = self.store.finish_request
        calls = 0
        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError('Injected terminal-result persistence failure')
            return original(*args, **kwargs)
        before = self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0]
        with patch.object(self.store, 'finish_request', side_effect=fail_once):
            self.assertEqual(self.run_generator().kind, 'FAILURE')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM entities').fetchone()[0], before)
        self.assertEqual(calls, 2)

    def test_selected_assessment_revocation_blocks_content_and_later_application(self):
        result = self.run_generator()
        self.accept(result)
        before = self.store.read_context(AUTH)
        self.models.callback = lambda data: self.service.decide(AUTH, 'admin', result.proposal_refs[0],
            'REJECT', 'Revoke the selected assessment during content generation')
        self.assertEqual(self.run_generator('TEACHER_CONTENT', request_id='teacher-revoked').kind, 'FAILURE')
        self.assertEqual(self.store.read_context(AUTH), before)

    def test_final_application_rechecks_generator_input_approvals_under_write_lock(self):
        assessment = self.run_generator()
        self.accept(assessment)
        teacher = self.run_generator('TEACHER_CONTENT', request_id='teacher')
        self.service.decide(AUTH, 'admin', teacher.proposal_refs[0], 'APPROVE', 'Review exact Teacher output')
        original = self.store.commit_change
        def revoke_before_lock(*args, **kwargs):
            self.service.decide(AUTH, 'admin', assessment.proposal_refs[0], 'REJECT', 'Concurrent input revocation')
            return original(*args, **kwargs)
        before = self.store.read_context(AUTH)
        with patch.object(self.store, 'commit_change', side_effect=revoke_before_lock), self.assertRaises(ValueError):
            self.service.apply(AUTH, 'admin', teacher.proposal_refs[0], 'revoked-teacher')
        self.assertEqual(self.store.read_context(AUTH), before)
        self.assertIsNone(self.store.operation_result('revoked-teacher', AUTH))

    def test_concurrent_project_revision_is_rejected_without_rebase(self):
        self.assessment()
        command = self.command('TEACHER_CONTENT')
        def callback(data):
            other_models = SyntheticModels()
            with LearningStore(self.path) as other:
                service = LearningService(other, load_contract(), self.service.policy, Mock())
                result = service.generate_project_assessments(AUTH, 'admin', self.command(),
                    request_id='other-assessment', authoring_factory=other_models.factory)
                self.assertEqual(result.kind, 'PROPOSAL')
                service.decide(AUTH, 'admin', result.proposal_refs[0], 'APPROVE', 'Concurrent exact assessment revision')
                service.apply(AUTH, 'admin', result.proposal_refs[0], 'other-assessment')
        self.models.callback = callback
        self.assertEqual(self.run_generator('TEACHER_CONTENT', command, request_id='stale-teacher').kind, 'FAILURE')
        self.models.callback = None
        with self.assertRaises(StateConflict):
            self.run_generator('TEACHER_CONTENT', command.model_copy(update={'base_context': self.store.read_context(AUTH).ref}), request_id='stale-project')

    def test_replay_still_requires_current_authorization_and_failure_replay_is_exact(self):
        self.models.verdict = self.models.verdict.model_copy(update={'verdict': 'UNCERTAIN'})
        command = self.command()
        result = self.run_generator(command=command)
        calls = len(self.models.calls)
        self.assertEqual(self.run_generator(command=command), result)
        self.assertEqual(len(self.models.calls), calls)
        policy = self.service.policy.model_dump()
        policy['subjects']['admin']['actions'][AUTH] = ['read']
        self.service.policy = type(self.service.policy).model_validate(policy)
        with self.assertRaises(ValueError):
            self.run_generator(command=command)

    def test_ordering_and_outcome_coverage_are_validated_for_multiple_units(self):
        # Read an actual reserved input, then extend its synthetic syllabus/unit
        # pair to test the checks independently of any source-model side effect.
        self.run_generator()
        data = self.models.inputs[0]
        second = data.units[0].model_copy(update={'key': 'second-unit'})
        artifact = data.syllabus.artifact
        second_draft = artifact.draft.units[0].model_copy(update={'key': 'second-unit'})
        syllabus = data.syllabus.model_copy(update={'artifact': artifact.model_copy(update={
            'draft': artifact.draft.model_copy(update={'units': (*artifact.draft.units, second_draft)})})})
        data = GenerationInput.model_validate(data.model_copy(update={'units': (*data.units, second), 'syllabus': syllabus}).model_dump(mode='json'))
        from tests.generator_fixtures import synthetic_draft
        from aimpro.generators import checked_draft
        draft = synthetic_draft(data)
        checked_draft(data, draft)
        with self.assertRaises(ValueError):
            checked_draft(data, draft.model_copy(update={'units': tuple(reversed(draft.units))}))
        with self.assertRaises(ValueError):
            checked_draft(data, draft.model_copy(update={'units': draft.units[:1]}))

    def test_review_budget_and_wrong_typed_worker_output_do_not_create_proposals(self):
        self.run_generator()
        data = self.models.inputs[0]
        dispatcher, lead, _ = self.models.factory()
        calls = len(self.models.calls)
        with self.assertRaisesRegex(ValueError, 'budget'):
            generate(data, dispatcher=dispatcher, lead=lead, max_context_chars=10)
        self.assertEqual(self.models.calls[calls:], ['assessment-designer'])
        from learning.outputs import WorkerOutput
        self.models.transform = lambda data, draft: WorkerOutput(kind='CHANGE_PROPOSAL', content='Wrong output contract')
        self.assertEqual(self.run_generator(request_id='untyped').kind, 'FAILURE')

    def test_material_outcomes_follow_actual_item_usage_across_units(self):
        from dataclasses import replace
        from aimpro.generation_state import revision
        from aimpro.generators import UnitInput
        from tests.generator_fixtures import synthetic_draft
        self.assessment()
        self.run_generator('TEACHER_CONTENT', request_id='teacher')
        data = self.models.inputs[-1]
        context = self.service._context(AUTH, 'admin')
        extra_outcome = self.author.outcome.model_copy(update={'id': 'second-explicit-outcome'})
        extra_node = data.units[0].node.model_copy(update={'id': 'second-explicit-unit',
            'fields': {**data.units[0].node.fields, 'outcomes': [extra_outcome.ref.model_dump()]}})
        artifact = data.syllabus.artifact
        extra_draft = artifact.draft.units[0].model_copy(update={'key': 'second-unit'})
        data = data.model_copy(update={
            'units': (*data.units, UnitInput(key='second-unit', node=extra_node)),
            'syllabus': data.syllabus.model_copy(update={'artifact': artifact.model_copy(update={
                'draft': artifact.draft.model_copy(update={'units': (*artifact.draft.units, extra_draft)})})})})
        context = replace(context, snapshot=replace(context.snapshot,
            entities={**context.snapshot.entities, extra_outcome.ref: extra_outcome, extra_node.ref: extra_node}))
        manifest = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course').manifest
        draft = synthetic_draft(data)
        bundle = revision(context, manifest, data, draft, self.models.verdict)
        resources = [e for e in bundle.candidates if e.type == 'Resource' and e.id != bundle.artifacts[0].resource.id]
        self.assertEqual(len(resources), 6)
        self.assertTrue(all(len(r.fields['outcomes']) == 1 for r in resources))
        self.assertEqual({canonical_outcome(r) for r in resources},
                         {self.author.outcome.ref, extra_outcome.ref})

    def test_cli_generators_and_exact_replay_use_real_service(self):
        policy = Path(self.temp.name) / 'policy.json'
        policy.write_text(self.service.policy.model_dump_json())
        bundle = Path(self.temp.name) / 'command.json'
        args = ['--db', str(self.path), '--policy', str(policy), '--subject', 'admin', '--context', AUTH]
        for role, command_name in (('ASSESSMENT', 'assessments'), ('TEACHER_CONTENT', 'teacher'), ('TRAINER_CONTENT', 'trainer')):
            bundle.write_text(self.command(role).model_dump_json())
            with patch('learning.__main__._aimpro_authoring', side_effect=self.models.factory):
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main([*args, 'generate-project-' + command_name, str(bundle), '--request-id', 'cli-' + role]), 0)
                result = json.loads(output.getvalue())
                with patch('learning.__main__._aimpro_authoring', side_effect=AssertionError('Replay must not build clients')):
                    replay = StringIO()
                    with redirect_stdout(replay):
                        self.assertEqual(main([*args, 'generate-project-' + command_name, str(bundle), '--request-id', 'cli-' + role]), 0)
                    self.assertEqual(json.loads(replay.getvalue()), result)
            proposal = self.store.read(EntityRef.model_validate(result['proposal_refs'][0]), owner=AUTH)
            self.author.review_and_apply(AUTH, proposal, 'cli-' + role)


def selection_project(service):
    return service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course').project


def replace_item(draft, item):
    unit = draft.units[0].model_copy(update={'items': (item,)})
    return draft.model_copy(update={'units': (unit, *draft.units[1:])})


def canonical_outcome(resource):
    return EntityRef.model_validate(resource.fields['outcomes'][0])
