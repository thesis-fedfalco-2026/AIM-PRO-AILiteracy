"""Progressive refinement of a syllabus (S09b, D18): the syllabus in words, revisions, edits and comparisons.

A syllabus proposal is read in words: its units with the texts of their target,
competencies, practices and cited excerpts. It is compared with the proposal it
refines and with the course's applied syllabus, units paired by learning target.
A revision request reaches the Curator through a revision job; a teacher's edit
is recorded here, without a model, as a new proposal by that teacher.
"""

from learning.contracts import Entity, EntityRef
from tests.services.job_fixtures import prepared_syllabus_job, revision_job
from tests.services.test_authoring_exports_api import COURSE
from tests.services.test_authoring_sources_api import SourcesApiCase
from tests.syllabus_fixtures import revised_syllabus, syllabus


REASON = 'Add a unit where participants explain two choices.'
STALE = 'The course changed after this syllabus proposal; prepare the sources and generate the syllabus again'


class SyllabusApiCase(SourcesApiCase):
    def curator(self, request_id='curator-1', job=None):
        self.body(self.queue(request_id, job or {'kind': 'generate-aimpro-syllabus', 'project': self.export,
                                                 'source_scope': 'wp3', 'query': 'prompting', 'k': 3}))
        self.run_worker()
        done = self.job(request_id)
        self.assertEqual(done['status'], 'PROPOSED', done)
        return EntityRef.model_validate(done['proposal_refs'][0])

    def key(self, proposal):
        for item in self.body(self.staff.get(f'/contexts/{COURSE}/pending-proposals'))['proposals']:
            if item['proposal']['id'] == proposal.id:
                return Entity.model_validate(item['proposal']).ref, item['review_payload_key']
        raise AssertionError('not pending')

    def view(self, proposal, client=None):
        return (client or self.staff).get(f'/contexts/{COURSE}/syllabus-proposals/{proposal.id}')

    def edit(self, proposal, draft, request_id='edit-1', client=None, csrf=True):
        return self.post(client or self.staff, f'/contexts/{COURSE}/syllabus-edits',
                         {'request_id': request_id, 'proposal': proposal.id, 'draft': draft}, csrf=csrf)

    def approve_apply(self, proposal, operation):
        ref, key = self.key(proposal)
        self.ok(self.decide(self.staff, COURSE, ref, key))
        self.ok(self.apply(self.staff, COURSE, ref, operation))


class SyllabusViewTest(SyllabusApiCase):
    # Acceptance: every syllabus proposal has a teacher view in words.
    def test_a_syllabus_proposal_is_read_in_words(self):
        proposal = self.curator()
        view = self.body(self.view(proposal))
        record = view['syllabus']
        self.assertEqual((record['proposal']['id'], record['status'], record['responsible']),
                         (proposal.id, 'AWAITING_DECISION', 'admin'))
        self.assertEqual(record['draft'], syllabus().model_dump(mode='json'))
        self.assertTrue(record['reviewed_by_agent'])
        self.assertEqual((record['edited_by'], record['revision_reasons']), (None, []))
        [target] = view['targets']
        unit = record['draft']['units'][0]
        self.assertEqual(target['id'], unit['source_target_id'])
        self.assertIn('construct a first prompt', target['statement'])
        self.assertEqual([c['name'] for c in target['competencies']], ['AI Interaction & Prompting'])
        self.assertEqual({p['id'] for p in target['practices']}, set(unit['source_practice_ids']))
        self.assertTrue(all(p['name'] and p['text'] for p in target['practices']))
        [excerpt] = view['excerpts']
        self.assertEqual((excerpt['resource_id'], excerpt['resource_version'], excerpt['document_id']),
                         ('wp3:test', 'v1', 'chunk-1'))
        self.assertTrue(excerpt['text'])
        # Retrieved by a query: no purpose or limitations were written for it.
        self.assertEqual((excerpt['purpose'], excerpt['limitations']), (None, []))
        # A course without a syllabus: every unit is added.
        self.assertEqual((view['course_design'], view['current'], view['refined']), ('NONE', None, None))
        self.assertEqual([u['status'] for u in view['compared_with_current']['units']], ['ADDED'])
        self.assertIsNone(view['compared_with_refined'])

    def test_excerpts_of_prepared_sources_carry_their_purpose_and_limitations(self):
        self.prepare()
        self.body(self.choose('preparation-1', 'ACCEPTED'))
        proposal = self.curator(job=prepared_syllabus_job(self.export, 'preparation-1'))
        [excerpt] = self.body(self.view(proposal))['excerpts']
        self.assertEqual((excerpt['purpose'], excerpt['limitations']), ('Task, audience and tone.', ['Synthetic excerpt.']))

    def test_only_a_syllabus_proposal_of_a_staff_member_is_read(self):
        proposal = self.curator()
        self.refused(self.view(proposal, self.learner), 403, 'forbidden')
        self.refused(self.staff.get(f'/contexts/{COURSE}/syllabus-proposals/proposal-unknown'), 404, 'not_found')


class RefinementTest(SyllabusApiCase):
    # Acceptance: a revision request carries its reason to the Curator; the new proposal is compared with the previous.
    def test_a_revision_request_reaches_the_curator_and_is_compared_with_the_previous_proposal(self):
        first = self.curator()
        ref, key = self.key(first)
        self.ok(self.decide(self.staff, COURSE, ref, key, decision='REQUEST_REVISION', reason=REASON))
        second = self.curator('revision-1', revision_job(first.id))
        view = self.body(self.view(second))
        self.assertEqual(view['syllabus']['revision_reasons'], [REASON])
        self.assertEqual(view['syllabus']['draft'], revised_syllabus().model_dump(mode='json'))
        self.assertEqual(view['refined']['proposal']['id'], first.id)
        self.assertEqual(view['refined']['status'], 'DRAFT')
        compared = view['compared_with_refined']
        self.assertTrue(compared['title_changed'])
        self.assertEqual([(u['status'], u['changed_fields']) for u in compared['units']],
                         [('CHANGED', ['purpose']), ('ADDED', [])])

    # Acceptance: a teacher's edit is a new proposal by that teacher, compared with the one it edits.
    def test_an_edit_is_recorded_as_a_new_proposal_by_the_teacher(self):
        first = self.curator()
        draft = revised_syllabus().model_dump(mode='json')
        before = self.digests()
        self.refused(self.edit(first, draft, csrf=False), 403, 'forbidden')
        self.refused(self.edit(first, draft, client=self.learner), 403, 'forbidden')
        self.assertEqual(self.digests(), before)
        edited = self.body(self.edit(first, draft))
        proposal = EntityRef.model_validate(edited['proposal'])
        self.assertEqual(self.body(self.edit(first, draft)), edited)
        view = self.body(self.view(proposal))
        record = view['syllabus']
        self.assertEqual((record['responsible'], record['edited_by'], record['reviewed_by_agent']),
                         ('admin', 'admin', False))
        self.assertIsNone(record['review'])
        self.assertEqual(view['refined']['proposal']['id'], first.id)
        self.assertEqual([u['status'] for u in view['compared_with_refined']['units']], ['CHANGED', 'ADDED'])
        self.key(proposal)

    def test_an_edit_that_fails_the_checks_of_a_generated_syllabus_is_refused_with_a_fixed_reason(self):
        first = self.curator()
        draft = syllabus().model_dump(mode='json')
        draft['units'][0]['source_practice_ids'] = ['invented']
        before = self.digests()
        detail = self.refused(self.edit(first, draft), 422, 'validation')
        self.assertEqual(detail, 'Syllabus unit practices are outside its source target')
        self.assertEqual(self.digests(), before)

    # Acceptance: after each applied step the course shows the applied syllabus.
    def test_each_applied_step_becomes_the_course_syllabus_it_is_compared_with(self):
        first = self.curator()
        self.approve_apply(first, 'apply-1')
        edited = EntityRef.model_validate(self.body(self.edit(first, revised_syllabus().model_dump(mode='json')))['proposal'])
        view = self.body(self.view(edited))
        self.assertEqual((view['course_design'], view['current']['proposal']['id']), ('SYLLABUS', first.id))
        self.assertEqual([u['status'] for u in view['compared_with_current']['units']], ['CHANGED', 'ADDED'])
        self.approve_apply(edited, 'apply-2')
        summary = self.body(self.staff.get(f'/contexts/{COURSE}'))
        context = Entity.model_validate(summary['context'])
        design = next(Entity.model_validate(e) for e in summary['entities']
                      if e['type'] == 'LearningDesign' and e['id'] == context.fields['learningDesign']['id'])
        self.assertEqual(design.fields['name'], revised_syllabus().title)
        # The first proposal is no longer the course's step: a revision of it is refused as stale.
        self.refused(self.edit(first, syllabus().model_dump(mode='json'), 'edit-2'), 422, 'validation')
        self.assertEqual(self.body(self.view(edited))['current']['proposal']['id'], edited.id)

    def test_a_revision_after_another_applied_step_is_rejected_as_stale(self):
        first = self.curator()
        other = self.curator('curator-2')
        ref, key = self.key(first)
        self.ok(self.decide(self.staff, COURSE, ref, key, decision='REQUEST_REVISION', reason=REASON))
        self.approve_apply(other, 'apply-other')
        self.body(self.queue('revision-1', revision_job(first.id)))
        self.run_worker()
        done = self.job('revision-1')
        self.assertEqual((done['status'], done['detail']), ('REJECTED', STALE))
