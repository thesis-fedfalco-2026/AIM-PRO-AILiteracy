"""Source preparation as a job (S09a2, D22): discover, choose, prepare, accept, then the Curator.

A teacher writes queries; a discovery job runs them in the worker and records
the excerpts found. The teacher picks excerpts, with the purpose and the
limitations of each, and a preparation job fetches them exactly. The prepared
sources are not a proposal: the preparation job awaits the teacher's choice,
and only sources the teacher accepted ground a Curator job. Neither job builds
a model; the API only records commands and reads what the worker recorded.
"""

import hashlib
import os
from unittest.mock import patch

from aimpro.audit import DEFAULT_PROJECT
from learning.contracts import Entity, EntityRef
from services.jobs.store import JobStore
from tests.services.job_fixtures import discovery_job, prepared_syllabus_job
from tests.services.test_authoring_exports_api import COURSE, ExportsApiCase
from tests.test_aimpro_retrieval import response as corpus_response


NOT_ACCEPTED = 'The prepared sources have not been accepted by the teacher'


class SourcesApiCase(ExportsApiCase):
    def setUp(self):
        super().setUp()
        self.body(self.post(self.staff, '/courses', {'context_id': COURSE}))
        self.export = self.report(self.upload(DEFAULT_PROJECT.read_bytes(), COURSE))['export']

    def body(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        return response.json()

    def run_worker(self):
        from tests.synthetic_worker import main
        env = {'ALM_STORE': str(self.location), 'ALM_POLICY_DIR': str(self.policies),
               'ALM_JOBS_STORE': str(self.jobs_location), 'ALM_AIMPRO_EXPORTS': str(self.exports)}
        with patch.dict(os.environ, env):
            self.assertEqual(main(['--once']), 0)

    def queue(self, request_id, job, client=None):
        return self.post(client or self.staff, f'/contexts/{COURSE}/jobs', {'request_id': request_id, 'job': job})

    def job(self, request_id):
        return self.body(self.staff.get(f'/contexts/{COURSE}/jobs/{request_id}'))

    def choose(self, request_id, choice, client=None, csrf=True):
        return self.post(client or self.staff, f'/contexts/{COURSE}/jobs/{request_id}/choice', {'choice': choice},
                         csrf=csrf)

    def discover(self, request_id='discovery-1', *queries):
        self.body(self.queue(request_id, discovery_job(*queries)))
        self.run_worker()
        self.assertEqual(self.job(request_id)['status'], 'COMPLETED')
        return self.body(self.staff.get(f'/contexts/{COURSE}/source-discoveries/{request_id}'))

    def plan(self, found, picked=0):
        """The source plan a teacher builds in the studio from a discovery: its queries, the picked excerpts."""
        excerpt = found['excerpts'][picked]
        return {'source_sha256': self.export['sha256'], 'source_scope': found['source_scope'],
                'queries': found['queries'],
                'documents': [{key: excerpt[key] for key in
                               ('resource_id', 'resource_version', 'document_id', 'content_sha256')} |
                              {'purpose': 'Task, audience and tone.', 'limitations': ['Synthetic excerpt.']}]}

    def prepare(self, request_id='preparation-1'):
        found = self.discover()
        job = {'kind': 'prepare-aimpro-syllabus-sources', 'project': self.export, 'plan': self.plan(found)}
        self.body(self.queue(request_id, job))
        self.run_worker()
        self.assertEqual(self.job(request_id)['status'], 'AWAITING_CHOICE')
        return job


class SourcesCycleTest(SourcesApiCase):
    # Acceptance (API side of the browser test): prepare, review, accept, Curator, review and apply.
    def test_a_syllabus_is_built_on_sources_the_teacher_accepted(self):
        before = self.digests()
        found = self.discover('discovery-1', 'prompting', 'prompt clarity')
        # Discovery writes one request record and nothing else.
        self.assertEqual(self.digests()['entities'], before['entities'])
        document = corpus_response()['documents'][0]
        self.assertEqual(found['queries'], [{'query': 'prompting', 'k': 3}, {'query': 'prompt clarity', 'k': 3}])
        self.assertEqual(found['excerpts'], [{
            'resource_id': 'wp3:test', 'resource_version': 'v1', 'document_id': 'chunk-1',
            'content_sha256': hashlib.sha256(document['text'].encode()).hexdigest(),
            'title': 'Synthetic prompting guide', 'uri': 'https://example.org/guide', 'licence': 'CC-BY-4.0',
            'licence_verdict': None, 'text': document['text'], 'found_by': ['prompting', 'prompt clarity']}])
        self.assertEqual((found['unique_documents'], found['duplicate_hits']), (1, 1))

        job = {'kind': 'prepare-aimpro-syllabus-sources', 'project': self.export, 'plan': self.plan(found)}
        self.body(self.queue('preparation-1', job))
        self.run_worker()
        self.assertEqual(self.job('preparation-1')['status'], 'AWAITING_CHOICE')
        prepared = self.body(self.staff.get(f'/contexts/{COURSE}/source-preparations/preparation-1'))
        self.assertEqual((prepared['source_scope'], prepared['source_sha256']), ('wp3', self.export['sha256']))
        [excerpt] = prepared['excerpts']
        self.assertEqual((excerpt['document_id'], excerpt['text'], excerpt['licence']),
                         ('chunk-1', document['text'], 'CC-BY-4.0'))
        self.assertEqual((excerpt['purpose'], excerpt['limitations']), ('Task, audience and tone.', ['Synthetic excerpt.']))
        self.assertEqual(prepared['coverage_requirements'], [])

        accepted = self.body(self.choose('preparation-1', 'ACCEPTED'))
        self.assertEqual(accepted['status'], 'ACCEPTED')
        self.body(self.queue('curator-1', prepared_syllabus_job(self.export, 'preparation-1')))
        self.run_worker()
        done = self.job('curator-1')
        self.assertEqual(done['status'], 'PROPOSED', done)
        proposal = EntityRef.model_validate(done['proposal_refs'][0])
        [(pending, key)] = [(Entity.model_validate(item['proposal']).ref, item['review_payload_key'])
                            for item in self.body(self.staff.get(f'/contexts/{COURSE}/pending-proposals'))['proposals']]
        self.assertEqual(pending, proposal)
        self.ok(self.decide(self.staff, COURSE, proposal, key))
        self.ok(self.apply(self.staff, COURSE, proposal, 'apply-syllabus'))
        context = Entity.model_validate(self.body(self.staff.get(f'/contexts/{COURSE}'))['context'])
        self.assertTrue(context.fields.get('learningDesign'))

    # Acceptance: a replayed request id returns the same preparation and runs no retrieval again.
    def test_a_replayed_preparation_returns_the_same_job_and_preparation(self):
        job = self.prepare()
        waiting = self.job('preparation-1')
        prepared = self.body(self.staff.get(f'/contexts/{COURSE}/source-preparations/preparation-1'))
        self.assertEqual(self.body(self.queue('preparation-1', job)), waiting)
        with JobStore(self.jobs_location) as jobs:
            self.assertIsNone(jobs.claim())
        self.assertEqual(self.body(self.staff.get(f'/contexts/{COURSE}/source-preparations/preparation-1')), prepared)
        changed = {**job, 'plan': {**job['plan'], 'max_documents_per_resource': 2}}
        self.refused(self.queue('preparation-1', changed), 409, 'conflict')


class ChoiceTest(SourcesApiCase):
    # Acceptance: sources that were not accepted are never used by a Curator job.
    def test_a_curator_job_on_sources_not_accepted_is_refused_and_nothing_is_queued(self):
        self.prepare('preparation-1')
        self.prepare('preparation-2')
        self.body(self.choose('preparation-2', 'DECLINED'))
        for prepared in ('preparation-1', 'preparation-2', 'discovery-1', 'missing'):
            with self.subTest(prepared=prepared):
                detail = self.refused(self.queue(f'curator-{prepared}', prepared_syllabus_job(self.export, prepared)),
                                      409, 'conflict')
                self.assertEqual(detail, NOT_ACCEPTED)
        with JobStore(self.jobs_location) as jobs:
            self.assertIsNone(jobs.claim())

    def test_the_choice_is_made_once_by_the_teacher_who_prepared_the_sources(self):
        self.prepare()
        self.refused(self.choose('preparation-1', 'ACCEPTED', csrf=False), 403, 'forbidden')
        self.refused(self.choose('preparation-1', 'ACCEPTED', client=self.learner), 403, 'forbidden')
        self.refused(self.choose('missing', 'ACCEPTED'), 404, 'not_found')
        self.refused(self.choose('preparation-1', 'MAYBE'), 422, 'validation')
        self.assertEqual(self.job('preparation-1')['status'], 'AWAITING_CHOICE')
        accepted = self.body(self.choose('preparation-1', 'ACCEPTED'))
        # The same choice again returns the job; another choice is a conflict.
        self.assertEqual(self.body(self.choose('preparation-1', 'ACCEPTED')), accepted)
        self.refused(self.choose('preparation-1', 'DECLINED'), 409, 'conflict')

    def test_only_a_preparation_awaiting_the_choice_can_be_chosen(self):
        self.discover()
        self.refused(self.choose('discovery-1', 'ACCEPTED'), 409, 'conflict')
        self.body(self.queue('queued-1', discovery_job('another query')))
        self.refused(self.choose('queued-1', 'ACCEPTED'), 409, 'conflict')

    def test_a_preparation_of_another_subject_is_not_chosen_by_this_one(self):
        self.prepare()
        with JobStore(self.jobs_location) as jobs:
            jobs.submit(COURSE, 'other-1', 'someone-else', 'prepare-aimpro-syllabus-sources', {'kind': 'x'})
            jobs.claim()
            jobs.transition(COURSE, 'other-1', {'RUNNING'}, 'AWAITING_CHOICE')
        self.refused(self.choose('other-1', 'ACCEPTED'), 403, 'forbidden')


class ReadTest(SourcesApiCase):
    def test_the_jobs_of_a_course_are_listed_newest_first_without_their_results(self):
        self.prepare()
        listed = self.body(self.staff.get(f'/contexts/{COURSE}/jobs'))['jobs']
        self.assertEqual([(j['request_id'], j['status']) for j in listed],
                         [('preparation-1', 'AWAITING_CHOICE'), ('discovery-1', 'COMPLETED')])
        self.assertEqual(listed[0], self.job('preparation-1'))
        self.refused(self.learner.get(f'/contexts/{COURSE}/jobs'), 403, 'forbidden')

    def test_source_records_are_read_by_their_kind_and_otherwise_not_found(self):
        self.prepare()
        for path in ('source-discoveries/missing', 'source-discoveries/preparation-1',
                     'source-preparations/discovery-1'):
            with self.subTest(path=path):
                self.refused(self.staff.get(f'/contexts/{COURSE}/{path}'), 404, 'not_found')
        for path in ('source-discoveries/discovery-1', 'source-preparations/preparation-1'):
            with self.subTest(path=path):
                self.refused(self.learner.get(f'/contexts/{COURSE}/{path}'), 403, 'forbidden')

    def test_the_targets_of_an_export_list_their_practices_and_quotable_fields(self):
        sha = self.export['sha256']
        targets = self.body(self.staff.get(f'/contexts/{COURSE}/aimpro-exports/{sha}/targets'))
        self.assertEqual(targets['export'], self.export)
        self.assertEqual((targets['scenario'], targets['competencies']), ('SCN01', 'elena_usecase_competencies'))
        [target] = targets['targets']
        self.assertEqual(target['class_name'], 'LearningTarget')
        self.assertTrue(target['fields']['description'])
        self.assertTrue(target['practices'])
        for item in (target, *target['practices']):
            self.assertLessEqual(set(item['fields']), {'description', 'inPractice', 'rationale', 'contextDetails'})
        self.refused(self.staff.get(f'/contexts/{COURSE}/aimpro-exports/{"0" * 64}/targets'), 404, 'not_found')
        self.refused(self.staff.get(f'/contexts/{COURSE}/aimpro-exports/{sha}/targets',
                                    params={'scenario': 'NO-SUCH-SCENARIO'}), 422, 'validation')
        self.refused(self.learner.get(f'/contexts/{COURSE}/aimpro-exports/{sha}/targets'), 403, 'forbidden')

    def test_a_preparation_with_coverage_requirements_shows_them(self):
        from tests.test_syllabus_coverage import requirements
        from tests.syllabus_fixtures import source
        found = self.discover()
        wanted = [r.model_dump(mode='json') for r in requirements(source())]
        plan = {**self.plan(found), 'coverage_requirements': wanted}
        self.body(self.queue('preparation-1', {'kind': 'prepare-aimpro-syllabus-sources', 'project': self.export,
                                             'plan': plan}))
        self.run_worker()
        prepared = self.body(self.staff.get(f'/contexts/{COURSE}/source-preparations/preparation-1'))
        self.assertEqual(prepared['coverage_requirements'], wanted)
