"""Network-forbidden production Teacher generation, rendering and replay."""

import json
import re
import unittest
from unittest.mock import Mock

from pydantic import ValidationError

from aimpro.generation_state import GeneratedArtifact
from aimpro.generators import GenerationCommand, checked_draft
from aimpro.lead import ReviewError
from aimpro.teacher import render_teacher
from aimpro.teacher_contracts import (IllustrativeEmail, ProtectedCaseFact, TeacherPlan,
                                      TranscriptPeerLink)
from learning.decisions import proposal_candidates
from learning.store import StateConflict
from tests import test_authoring_generators as legacy
from tests.authoring_cycle_fixtures import AUTH


REASON = '  Historical approval with limitations.\nKeep the illustrative sample placeholder and unvalidated rubric.  '


class StructuredTeacherTest(unittest.TestCase):
    command = legacy.AuthoringGeneratorTest.command
    run_generator = legacy.AuthoringGeneratorTest.run_generator
    accept = legacy.AuthoringGeneratorTest.accept

    def setUp(self):
        legacy.AuthoringGeneratorTest.setUp(self)
        self.models.transform = legacy.AuthoringGeneratorTest.add_stimulus.__get__(self)
        result = self.run_generator(command=legacy.AuthoringGeneratorTest.stimulus_command(self))
        proposal = self.store.read(result.proposal_refs[0], owner=AUTH)
        self.service.decide(AUTH, 'admin', proposal.ref, 'APPROVE', REASON)
        self.service.apply(AUTH, 'admin', proposal.ref, 'apply-assessment')
        self.models.transform = None
        self.models.calls.clear()
        self.models.inputs.clear()
        self.factory.reset_mock()

    def teacher_command(self):
        command = self.command('TEACHER_CONTENT')
        syllabus = self.service.approved_project_syllabus(AUTH, 'admin', command.project)
        key = syllabus.artifact.units[0].key
        return command.model_copy(update={'teacher_plan': TeacherPlan(
            transcript_peers=(TranscriptPeerLink(transcript_key=key + ':transcript', peer_key=key + ':peer'),),
            protected_case_facts=(ProtectedCaseFact(assessment=command.assessments[0], unit_key=key,
                stimulus_key='comparison', quote='EXAMPLE-01'),))})

    def run_teacher(self, **kwargs):
        return self.run_generator('TEACHER_CONTENT', command=self.teacher_command(), request_id='structured', **kwargs)

    def package(self, result):
        proposal = self.store.read(result.proposal_refs[0], owner=AUTH)
        return GeneratedArtifact.model_validate_json(next(e for e in proposal_candidates(self.store, proposal)
            if e.type == 'Resource' and e.id.startswith('authoring-output:')).fields['contentOrLocator'])

    def test_rendering_review_and_replay_keep_original_and_exact_human_reason(self):
        lead = self.models.review
        reviews = []
        def review(prompt, response_format):
            reviews.append(json.loads(prompt.split('\nDATA\n')[1]))
            return lead(prompt, response_format)
        self.models.review = review
        result = self.run_teacher()
        self.assertEqual(result.kind, 'PROPOSAL')
        self.assertEqual(result.application_status, 'pending')
        self.assertEqual(self.models.calls, ['teaching-designer-structured', 'LEAD_REVIEW'])
        package = self.package(result)
        self.assertEqual(package.format_version, 2)
        data, draft = package.inputs, package.draft
        self.assertEqual(data.inputs[0].approved_review.reason, REASON)
        # The decision service's stored value is authoritative, including any normalization it performed.
        decision = self.store.read(data.inputs[0].receipt.decision, owner=AUTH)
        self.assertEqual(draft.approved_review_notes[0].reason, decision.fields['reason'])
        self.assertEqual(reviews[0]['draft']['original'], draft.original.model_dump(mode='json'))
        self.assertEqual(reviews[0]['draft']['approved_review_notes'][0]['reason'], decision.fields['reason'])
        example = next(m.content for m in draft.materials if m.key.endswith(':peer'))
        transcript = next(m.content for m in draft.materials if m.kind == 'TRANSCRIPT')
        for label in ('PEER PROMPT', 'ILLUSTRATIVE EMAIL'):
            pattern = '^' + label + r'\n(.*?)\nEND ' + label + r'(?:\n|$)'
            a = re.findall(pattern, example, re.M | re.S)
            b = re.findall(pattern, transcript, re.M | re.S)
            self.assertEqual(len(a), 1)
            self.assertEqual(a, b)
        self.assertNotIn(decision.fields['reason'], '\n'.join(m.content for m in draft.materials))
        self.assertEqual(render_teacher(data, draft.original), draft)
        self.assertEqual(checked_draft(data, draft), draft)
        before = self.store.db.total_changes
        self.factory.side_effect = AssertionError('Replay must not construct clients')
        self.assertEqual(self.run_teacher(), result)
        self.assertEqual(self.store.db.total_changes, before)
        with self.assertRaises(StateConflict):
            self.run_generator('TEACHER_CONTENT', command=self.teacher_command().model_copy(update={
                'teacher_plan': TeacherPlan()}), request_id='structured')

    def test_invalid_links_email_markers_prompt_and_case_reuse_stop_before_lead(self):
        for case in ('missing-email', 'unknown-peer', 'missing-scene', 'marker', 'prompt-reuse', 'case-reuse'):
            with self.subTest(case=case):
                def transform(data, draft):
                    raw = draft.model_dump(mode='json')
                    if case == 'missing-email':
                        del raw['peers'][0]['email']['closing']
                    elif case == 'unknown-peer':
                        raw['transcripts'][0]['parts'][-1]['peer_key'] = 'absent'
                    elif case == 'missing-scene':
                        raw['transcripts'][0]['parts'].pop()
                    elif case == 'marker':
                        raw['peers'][0]['email']['paragraphs'][0] = 'END ILLUSTRATIVE EMAIL'
                    elif case == 'prompt-reuse':
                        from aimpro.teacher import assessment_prompt_bodies
                        raw['comparisons'][0]['weak_prompt'] = assessment_prompt_bodies(data)[0]
                    else:
                        raw['peers'][0]['facts'][0]['value'] = 'EXAMPLE-01'
                    return type(draft).model_validate(raw)
                self.models.transform = transform
                self.models.calls.clear()
                result = self.run_generator('TEACHER_CONTENT', command=self.teacher_command(), request_id=case)
                self.assertEqual(result.kind, 'FAILURE')
                self.assertEqual(self.models.calls, ['teaching-designer-structured'])

    def test_negative_case_disclaimer_is_allowed_and_rendered_metadata_cannot_be_forged(self):
        def transform(data, draft):
            peer = draft.peers[0].model_copy(update={'notice': 'Do not use EXAMPLE-01 or Alex from the assessment.'})
            return draft.model_copy(update={'peers': (peer,)})
        self.models.transform = transform
        package = self.package(self.run_teacher())
        for altered in (package.draft.model_copy(update={'approved_review_notes': ()}),
                        package.draft.model_copy(update={'materials': tuple(reversed(package.draft.materials))})):
            with self.assertRaises(ReviewError):
                checked_draft(package.inputs, altered)
        with self.assertRaises(ValidationError):
            GeneratedArtifact.model_validate(dict(package.model_dump(mode='json'), format_version=1))

    def test_foreign_fact_anchor_is_rejected_before_reservation_or_factory(self):
        command = self.teacher_command()
        anchor = command.teacher_plan.protected_case_facts[0].model_copy(update={'quote': 'Not in selected assessment'})
        command = command.model_copy(update={'teacher_plan': command.teacher_plan.model_copy(update={
            'protected_case_facts': (anchor,)})})
        before = self.store.db.total_changes
        with self.assertRaises(ReviewError):
            self.run_generator('TEACHER_CONTENT', command=command, request_id='bad-anchor')
        self.factory.assert_not_called()
        self.assertEqual(self.store.db.total_changes, before)

    def test_typed_email_requires_every_part_and_rejects_extra_fields(self):
        for values in ({'subject': 'Incomplete'}, {'subject': ' ', 'salutation': 'Dear X',
                'paragraphs': ['Body'], 'closing': 'Regards', 'signature': 'X'},
                {'subject': 'Subject', 'salutation': 'Dear X', 'paragraphs': ['Body'],
                 'closing': 'Regards', 'signature': 'X', 'approved': True}):
            with self.assertRaises(ValidationError):
                IllustrativeEmail(**values)

    def test_legacy_command_serialization_and_package_remain_format_one(self):
        self.assertNotIn('teacher_plan', GenerationCommand.model_validate(self.command()).model_dump())
        result = self.run_generator('TEACHER_CONTENT', request_id='legacy')
        package = self.package(result)
        self.assertEqual(package.format_version, 1)
        self.assertNotIn('approved_review', package.inputs.inputs[0].model_dump())
        self.assertEqual(self.models.calls, ['teaching-designer', 'LEAD_REVIEW'])

    def test_explicit_synthetic_application_can_feed_trainer_without_learning_activation(self):
        result = self.run_teacher()
        package = self.package(result)
        self.accept(result, 'synthetic-apply-structured-teacher')
        view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        teacher = next(a.resource for a in view.manifest.artifacts if a.kind == 'TEACHER_CONTENT')
        command = self.command('TRAINER_CONTENT', shared_content=(teacher,))
        trainer = self.run_generator('TRAINER_CONTENT', command=command, request_id='trainer-after-structured')
        self.assertEqual(trainer.kind, 'PROPOSAL')
        self.assertEqual(package.format_version, 2)
        for kind in ('ResourceBinding', 'ActivityOccurrence', 'Evidence', 'Evaluation', 'LearningState'):
            self.assertFalse(self.store.owned(AUTH, kind))


if __name__ == '__main__':
    unittest.main()
