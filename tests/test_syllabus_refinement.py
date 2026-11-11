"""S09b: a syllabus proposal refined by a Curator revision or a teacher's edit, and compared unit by unit."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from aimpro.audit import DEFAULT_PROJECT
from aimpro.lead import ReviewError
from aimpro.syllabus import SyllabusDraft, SyllabusUnit
from aimpro.syllabus_compare import compare
from aimpro.syllabus_refinement import NO_REQUEST, STALE
from aimpro.syllabus_state import NOT_ACCEPTED, SyllabusArtifact, proposed
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.policies import ScopeGrant
from learning.service import LearningService
from learning.store import LearningStore
from tests.syllabus_fixtures import REJECTION, Curator, Reviewer, syllabus, verdict
from tests.test_aimpro_retrieval import response as search_response
from tests.test_learning_context import policy


def unit(key, target, title='Title', **fields):
    values = dict(key=key, title=title, source_target_id=target, source_competency_ids=('c',),
                  source_practice_ids=('p',), purpose='Purpose', planned_intents=('EXPLAIN',),
                  corpus_citations=({'resource_id': 'r', 'resource_version': 'v1', 'document_ids': ('d',),
                                     'supported_claim': 'Claim'},))
    values.update(fields)
    return SyllabusUnit.model_validate(values)


def draft(*units, title='Syllabus', gaps=()):
    return SyllabusDraft(source_sha256='s', metamodel_fingerprint='m', title=title, units=units, gaps=gaps)


def statuses(comparison):
    return [(row.status, (row.before or row.after).key if row.status == 'REMOVED' else row.after.key)
            for row in comparison.units]


class SyllabusComparisonTest(unittest.TestCase):
    def test_a_course_without_a_syllabus_gets_every_unit_added(self):
        after = draft(unit('a', 't1'), unit('b', 't1'), unit('c', 't2'), gaps=('No rubric',))
        comparison = compare(None, after)
        self.assertEqual(statuses(comparison), [('ADDED', 'a'), ('ADDED', 'b'), ('ADDED', 'c')])
        self.assertFalse(comparison.title_changed)
        self.assertFalse(comparison.order_changed)
        self.assertEqual(comparison.gaps_added, ('No rubric',))

    def test_units_are_paired_by_target_and_not_by_key_or_title(self):
        before = draft(unit('x', 't1', title='Old'), unit('y', 't2'))
        after = draft(unit('unit-0', 't1', title='New'), unit('unit-1', 't2'))
        rows = compare(before, after).units
        self.assertEqual([r.status for r in rows], ['CHANGED', 'UNCHANGED'])
        self.assertEqual(rows[0].changed_fields, ('title',))
        self.assertEqual((rows[0].before.title, rows[0].after.title), ('Old', 'New'))

    def test_several_units_on_one_target_are_paired_in_their_order(self):
        before = draft(unit('a', 't1'), unit('b', 't1', purpose='Second'), unit('c', 't2'))
        after = draft(unit('a', 't1', planned_intents=('EXPLAIN', 'PRACTICE')), unit('b', 't1', purpose='Second'),
                      unit('n', 't1', title='Third'), unit('c', 't2'))
        rows = compare(before, after).units
        self.assertEqual([r.status for r in rows], ['CHANGED', 'UNCHANGED', 'ADDED', 'UNCHANGED'])
        self.assertEqual(rows[0].changed_fields, ('planned_intents',))
        fewer = compare(after, before).units
        self.assertEqual([(r.status, r.target_id) for r in fewer],
                         [('CHANGED', 't1'), ('UNCHANGED', 't1'), ('REMOVED', 't1'), ('UNCHANGED', 't2')])
        self.assertEqual(fewer[2].before.title, 'Third')

    def test_every_compared_field_is_reported_in_order(self):
        old = unit('a', 't1')
        new = unit('a', 't1', title='T', purpose='P', planned_intents=('PRACTICE',), source_competency_ids=('c2',),
                   source_practice_ids=('p2',), corpus_citations=({'resource_id': 'r', 'resource_version': 'v1',
                                                                   'document_ids': ('d',), 'supported_claim': 'Other'},))
        self.assertEqual(compare(draft(old), draft(new)).units[0].changed_fields,
                         ('title', 'purpose', 'planned_intents', 'source_competency_ids', 'source_practice_ids',
                          'corpus_citations'))

    def test_a_removed_target_comes_last_and_reordering_is_reported(self):
        before = draft(unit('a', 't1'), unit('b', 't2'), unit('c', 't3'), title='Old', gaps=('g1',))
        after = draft(unit('c', 't3'), unit('a', 't1'), title='New', gaps=('g2',))
        comparison = compare(before, after)
        self.assertEqual([(r.status, r.target_id) for r in comparison.units],
                         [('UNCHANGED', 't3'), ('UNCHANGED', 't1'), ('REMOVED', 't2')])
        self.assertTrue(comparison.order_changed)
        self.assertTrue(comparison.title_changed)
        self.assertEqual((comparison.gaps_added, comparison.gaps_removed), (('g2',), ('g1',)))
        self.assertFalse(compare(before, before).order_changed)


class SyllabusRefinementTest(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = LearningStore(Path(temp.name) / 'state.sqlite')
        self.addCleanup(self.store.close)
        trusted = policy().model_copy(update={'scopes': {
            'wp3': ScopeGrant(contexts=['session'], subjects=['admin'], sources=['wp3'])}})
        self.service = LearningService(self.store, load_contract(), trusted,
                                       Mock(side_effect=AssertionError('Learning workers must not run')))
        self.service.bootstrap('session', 'admin')
        self.curator, self.reviewer = Curator(), Reviewer()
        self.factory = Mock(return_value=(self.curator, self.reviewer, None))
        self.search_factory = Mock(return_value=Mock(return_value=search_response()))

    def generate(self, request_id='syllabus'):
        response = self.service.generate_aimpro_syllabus('session', 'admin', DEFAULT_PROJECT, request_id=request_id,
            authoring_factory=self.factory, source_scope='wp3', query='prompting', k=3,
            search_factory=self.search_factory)
        self.assertEqual(response.kind, 'PROPOSAL')
        return response.proposal_refs[0]

    def request_revision(self, proposal, reason):
        self.service.decide('session', 'admin', proposal, 'REQUEST_REVISION', reason)

    def revise(self, proposal, request_id='revision'):
        return self.service.revise_aimpro_syllabus('session', 'admin', proposal.id, request_id=request_id,
                                                   authoring_factory=self.factory)

    def syllabus_of(self, proposal):
        return proposed(self.store, self.service._context('session', 'admin'), proposal.id)

    def revised(self, base):
        units = base.units
        return base.model_copy(update={'title': 'Revised syllabus', 'units': (
            units[0].model_copy(update={'purpose': 'Practice tone with a fictional supplier.'}),
            units[0].model_copy(update={'key': 'extra', 'title': 'Explain two choices'}))})

    def test_a_revision_request_carries_its_reason_to_the_curator(self):
        first = self.generate()
        self.request_revision(first, 'Add a unit where participants explain their choices.')
        self.curator.value = self.revised(self.curator.value)
        response = self.revise(first)
        self.assertEqual(response.kind, 'PROPOSAL')
        prompt = self.curator.calls[-1][1]
        self.assertIn('AIMPRO_SYLLABUS_REVISION', prompt)
        data = json.loads(prompt.split('\nDATA\n')[1])
        self.assertEqual(data['teacher_reasons'], ['Add a unit where participants explain their choices.'])
        self.assertEqual(data['previous_syllabus'], syllabus().model_dump(mode='json'))
        second = self.syllabus_of(response.proposal_refs[0])
        self.assertEqual(second.artifact.revises.id, first.id)
        self.assertEqual(second.artifact.revision_reasons, ('Add a unit where participants explain their choices.',))
        self.assertIsNotNone(second.artifact.review)
        self.assertIsNone(second.artifact.edited_by)
        self.assertEqual(second.proposal.fields['status'], 'AWAITING_DECISION')
        # No new search: the revision is built on the input of the proposal it revises.
        self.assertEqual(self.search_factory.call_count, 1)
        self.assertEqual(second.source, self.syllabus_of(first).source)
        rows = compare(self.syllabus_of(first).artifact.draft, second.artifact.draft).units
        self.assertEqual([r.status for r in rows], ['CHANGED', 'ADDED'])

    def test_the_whole_chain_of_reasons_reaches_the_next_revision(self):
        first = self.generate()
        self.request_revision(first, 'First reason')
        second = self.revise(first).proposal_refs[0]
        self.request_revision(second, 'Second reason')
        third = self.revise(second, 'revision-2').proposal_refs[0]
        data = json.loads(self.curator.calls[-1][1].split('\nDATA\n')[1])
        self.assertEqual(data['teacher_reasons'], ['First reason', 'Second reason'])
        self.assertEqual(self.syllabus_of(third).artifact.revision_reasons, ('First reason', 'Second reason'))
        self.assertEqual(self.syllabus_of(third).artifact.revises.id, second.id)

    def test_a_revision_needs_a_revision_request_and_runs_no_model_without_one(self):
        first = self.generate()
        built = self.factory.call_count
        with self.assertRaisesRegex(ReviewError, NO_REQUEST):
            self.revise(first)
        self.service.decide('session', 'admin', first, 'REJECT', 'Not this one')
        with self.assertRaisesRegex(ReviewError, NO_REQUEST):
            self.revise(first)
        self.assertEqual(self.factory.call_count, built)
        self.assertIsNone(self.store.request_record('revision', 'session'))

    def test_a_revision_after_another_applied_step_is_refused_as_stale(self):
        first = self.generate()
        other = self.generate('other')
        self.request_revision(first, 'Shorter units')
        self.service.decide('session', 'admin', other, 'APPROVE', 'Apply this one')
        self.service.apply('session', 'admin', other, 'apply-other')
        built = self.factory.call_count
        with self.assertRaisesRegex(ReviewError, STALE):
            self.revise(first)
        self.assertEqual(self.factory.call_count, built)

    def test_a_replayed_revision_returns_the_same_proposal_without_a_model(self):
        first = self.generate()
        self.request_revision(first, 'Reason')
        response = self.revise(first)
        built = self.factory.call_count
        self.assertEqual(self.revise(first), response)
        self.assertEqual(self.factory.call_count, built)

    def test_a_failed_revision_is_recorded_with_its_fixed_reason_and_no_proposal(self):
        first = self.generate()
        self.request_revision(first, 'Reason')
        self.curator.value = self.curator.value.model_copy(update={'source_sha256': 'other'})
        response = self.revise(first)
        self.assertEqual(response.kind, 'FAILURE')
        self.assertIn('Syllabus fingerprints do not match the source', response.content)
        self.assertEqual(len([p for p in self.store.owned('session', 'ChangeProposal')]), 1)

    def test_a_rejected_revision_is_retried_and_its_review_receives_the_reasons(self):
        first = self.generate()
        self.request_revision(first, 'First reason')
        second = self.revise(first).proposal_refs[0]
        self.request_revision(second, 'Second reason')
        self.reviewer.calls, self.reviewer.queue = [], [REJECTION]
        response = self.revise(second, 'revision-2')
        self.assertEqual(response.kind, 'PROPOSAL')
        self.assertEqual([a.review for a in response.attempts], [REJECTION, verdict()])
        self.assertEqual(self.service.aimpro_syllabus_request('session', 'admin', 'revision-2'), response)
        for prompt, _ in self.reviewer.calls:
            data = json.loads(prompt.split('\nDATA\n')[1])
            self.assertEqual(data['teacher_reasons'], ['First reason', 'Second reason'])
            self.assertEqual(data['previous_syllabus'], self.syllabus_of(second).artifact.draft.model_dump(mode='json'))
        retry = json.loads(self.curator.calls[-1][1].split('\nDATA\n')[1])
        self.assertEqual(retry['review_feedback'], {'review': REJECTION.model_dump(mode='json')})
        self.assertEqual(retry['teacher_reasons'], ['First reason', 'Second reason'])

    def test_a_revision_rejected_at_every_attempt_proposes_its_last_draft_with_the_notice(self):
        # Owner decision (issue #112): the teacher decides on a revision the review agent did not accept.
        first = self.generate()
        self.request_revision(first, 'Reason')
        self.reviewer.value = REJECTION
        with self.assertLogs('agent_system', 'WARNING') as logged:
            response = self.revise(first)
        self.assertEqual((response.kind, response.content, response.notice),
                         ('PROPOSAL', 'The refined syllabus awaits human review.', NOT_ACCEPTED))
        self.assertEqual(len(response.attempts), 3)
        self.assertNotIn(REJECTION.reason, '\n'.join(logged.output))
        self.assertEqual(self.revise(first), response)
        self.assertEqual(len(self.store.owned('session', 'ChangeProposal')), 2)

    def edit(self, proposal, value, request_id='edit'):
        return self.service.edit_aimpro_syllabus('session', 'admin', proposal.id, value, request_id=request_id)

    def test_an_edit_is_a_new_proposal_by_the_teacher_not_reviewed_by_the_agent(self):
        first = self.generate()
        edited = self.revised(self.syllabus_of(first).artifact.draft)
        built = self.factory.call_count
        response = self.edit(first, edited.model_dump(mode='json'))
        self.assertEqual(self.factory.call_count, built)
        found = self.syllabus_of(response.proposal_refs[0])
        self.assertEqual(found.proposal.provenance.responsible, 'admin')
        self.assertEqual(found.artifact.edited_by, 'admin')
        self.assertIsNone(found.artifact.review)
        self.assertEqual(found.artifact.revises.id, first.id)
        self.assertEqual(found.artifact.draft, edited)
        self.assertEqual(found.syllabus.fields['title'], 'Teacher-edited syllabus draft: Revised syllabus')
        self.assertIn("teacher's edit", found.proposal.fields['proposedChange'])
        # The edited proposal stays pending beside the one it edits; the teacher decides both.
        self.assertEqual(self.syllabus_of(first).proposal.fields['status'], 'AWAITING_DECISION')
        self.assertEqual(self.edit(first, edited), response)

    def test_an_edit_passes_the_same_checks_as_a_generated_syllabus(self):
        first = self.generate()
        base = self.syllabus_of(first).artifact.draft
        u = base.units[0]
        for changed in (
            base.model_copy(update={'units': (u.model_copy(update={'source_target_id': 'invented'}),)}),
            base.model_copy(update={'units': (u.model_copy(update={'source_practice_ids': ('invented',)}),)}),
            base.model_copy(update={'units': (u, u)}),
            base.model_copy(update={'source_sha256': 'other'}),
        ):
            with self.subTest(changed=changed), self.assertRaises(ReviewError):
                self.edit(first, changed)
            self.assertIsNone(self.store.request_record('edit', 'session'))
        self.assertEqual(len(self.store.owned('session', 'ChangeProposal')), 1)

    def test_an_applied_edit_resolves_as_the_course_syllabus_and_can_be_refined_again(self):
        first = self.generate()
        edited = self.revised(self.syllabus_of(first).artifact.draft)
        proposal = self.edit(first, edited).proposal_refs[0]
        self.service.decide('session', 'admin', proposal, 'APPROVE', 'My own syllabus')
        self.service.apply('session', 'admin', proposal, 'apply-edit')
        root = self.store.read_context('session')
        approved = self.service.approved_aimpro_syllabus('session', 'admin', root.fields['learningDesign'])
        self.assertEqual(approved.artifact.draft, edited)
        self.assertIsNone(approved.artifact.review)
        # The course is at the step the edit applied: editing it again is allowed; the first proposal is stale.
        again = self.edit(proposal, edited.model_copy(update={'title': 'Third'}), 'edit-2').proposal_refs[0]
        found, refined, current, design = self.service.aimpro_syllabus_proposal('session', 'admin', again.id)
        self.assertEqual((refined.proposal.id, current.proposal.id, design), (proposal.id, proposal.id, 'SYLLABUS'))
        self.assertEqual(found.artifact.draft.title, 'Third')
        with self.assertRaisesRegex(ReviewError, STALE):
            self.edit(first, edited, 'edit-3')

    def test_the_proposal_view_names_what_it_refines_and_the_course_design(self):
        first = self.generate()
        found, refined, current, design = self.service.aimpro_syllabus_proposal('session', 'admin', first.id)
        self.assertEqual((refined, current, design), (None, None, 'NONE'))
        self.assertIsNone(found.trace)
        with self.assertRaises(ValueError):
            self.service.aimpro_syllabus_proposal('session', 'learner', first.id)
        with self.assertRaises(ValueError):
            self.service.aimpro_syllabus_proposal('session', 'admin', 'proposal-unknown')

    def test_earlier_syllabus_payloads_keep_their_exact_shape(self):
        first = self.generate()
        payload = next(c for c in proposal_candidates(self.store, self.store.read(first, owner='session'))
                       if c.id.endswith(':syllabus'))
        raw = json.loads(payload.fields['contentOrLocator'])
        self.assertEqual(set(raw), {'format', 'format_version', 'context_id', 'curator', 'outline',
                                    'source_snapshot', 'units', 'draft', 'review'})
        artifact = SyllabusArtifact.model_validate(raw)
        with self.assertRaises(ValueError):
            SyllabusArtifact.model_validate({**raw, 'review': None})
        with self.assertRaises(ValueError):
            SyllabusArtifact.model_validate({**raw, 'edited_by': 'admin'})
        self.assertEqual(json.loads(artifact.model_dump_json()), raw)


if __name__ == '__main__':
    unittest.main()
