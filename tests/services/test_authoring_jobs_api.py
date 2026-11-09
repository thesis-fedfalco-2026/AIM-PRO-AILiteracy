"""Agent job endpoints (S08): queue a generation, follow it, abandon it.

The API authorizes a job command, records it in the jobs store and returns; it
never builds a model. The worker (here run in the test, with synthetic models)
runs the existing service method; the resulting proposal reaches the review
inbox. Progress is a server-sent-events stream of content-free events.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from learning.contracts import Entity, EntityRef
from learning.service import ABANDONED_CONTENT
from learning.store import LearningStore
from services.api_common.settings import ApiSettings
from services.authoring_api.app import create_app
from services.jobs.store import JobStore, StatusEvent
from agent_system.events import Event
from tests.authoring_cycle_fixtures import AUTH, DELIVERY_TWO
from tests.seed import build_seed
from tests.services.job_fixtures import (REQUIREMENT, SyntheticAgents, evaluator_command, evaluator_job,
                                         export_directory, worker)
from tests.services.course_fixtures import module_settings
from tests.services.oidc_fixtures import ISSUER, MAPPED_SUBJECT, NO_NETWORK, FakeProvider, auth_settings, write_identity_map
from tests.services.test_authoring_review_api import LEARNER_SUBJECT, ReviewApiCase
from tests.store_backends import block_network


class Interrupted(BaseException):
    """The worker process stops in the middle of a run (a crash, a kill)."""


def parse_stream(text):
    """``(id, event, data)`` of each server-sent event; keep-alive comments are skipped."""
    found = []
    for block in text.split('\n\n'):
        fields = dict(line.split(': ', 1) for line in block.splitlines() if line and not line.startswith(':'))
        if fields:
            found.append((fields.get('id'), fields.get('event'), fields.get('data')))
    return found


class JobsApiTest(ReviewApiCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.location = self.root / 'seed.sqlite'
        self.seed = build_seed(self.root / 'seed', self.location)
        self.policies = self.root / 'seed' / self.seed.policy_dir
        self.policy_file = self.policies / 'architecture-policy-1.json'
        self.jobs_location = self.root / 'jobs.sqlite'
        self.agents = SyntheticAgents(export_directory(self.root))
        self.jobs = JobStore(self.jobs_location)
        self.addCleanup(self.jobs.close)
        self.worker = worker(self.location, self.policies, self.jobs, self.agents, strict_events=True)
        self.start_api()

    def start_api(self):
        self.provider = FakeProvider()
        identities = write_identity_map(self.root,
            {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'},
            {'issuer': ISSUER, 'subject': LEARNER_SUBJECT, 'subject_key': 'learner'})
        settings = ApiSettings(auth=auth_settings(), identity_map=identities, store=str(self.location),
                               policy_dir=self.policies, jobs_store=str(self.jobs_location),
                               job_poll_seconds=0.01, job_stream_seconds=5, **module_settings(self.root))
        self.app = create_app(settings, transport=self.provider.transport)
        self.staff = self.signed_in(MAPPED_SUBJECT)
        self.learner = self.signed_in(LEARNER_SUBJECT)

    def evaluator(self, requirements=(REQUIREMENT,)):
        return evaluator_job(evaluator_command(self.location, self.seed.project, requirements))

    def queue(self, request_id, job=None, client=None, context_id=AUTH, csrf=True):
        return self.post(client or self.staff, f'/contexts/{context_id}/jobs',
                         {'request_id': request_id, 'job': job or self.evaluator()}, csrf=csrf)

    def job(self, response, status=None):
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        body = response.json()
        if status is not None:
            self.assertEqual(body['status'], status)
        return body

    def stream(self, request_id, client=None, **headers):
        response = (client or self.staff).get(f'/contexts/{AUTH}/jobs/{request_id}/events', headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.headers['content-type'].startswith('text/event-stream'))
        return response.text

    # Acceptance: a queued Evaluator job ends as a pending proposal visible in the inbox.
    def test_a_queued_evaluator_job_ends_as_a_pending_proposal_in_the_inbox(self):
        before = self.digests()
        queued = self.job(self.queue('job-1'), 'QUEUED')
        self.assertEqual((queued['context_id'], queued['request_id'], queued['subject_key']), (AUTH, 'job-1', 'admin'))
        self.assertEqual(queued['job'], self.evaluator())
        self.assertEqual((queued['proposal_refs'], queued['detail']), ([], None))
        # Queuing writes nothing in the ALM store and builds no model.
        self.assertEqual((self.digests(), self.agents.built), (before, []))
        self.assertEqual(self.job(self.staff.get(f'/contexts/{AUTH}/jobs/job-1'), 'QUEUED'), queued)

        self.worker.run_once()
        done = self.job(self.staff.get(f'/contexts/{AUTH}/jobs/job-1'), 'PROPOSED')
        proposal = EntityRef.model_validate(done['proposal_refs'][0])
        self.assertEqual(len(done['proposal_refs']), 1)
        inbox = [Entity.model_validate(item['proposal']).ref
                 for item in self.staff.get(f'/contexts/{AUTH}/pending-proposals').json()['proposals']]
        self.assertEqual(inbox[0], proposal)
        self.assertIn(self.seed.pending_proposals[AUTH][0], inbox)

    # Acceptance: a replayed request_id returns the same job and constructs no model.
    def test_a_replayed_request_id_returns_the_same_job_and_constructs_no_model(self):
        first = self.job(self.queue('job-1'))
        self.assertEqual(self.job(self.queue('job-1')), first)
        self.worker.run_once()
        calls = list(self.agents.models.calls)
        done = self.job(self.queue('job-1'), 'PROPOSED')
        self.assertEqual({k: v for k, v in done.items() if k not in ('status', 'proposal_refs', 'updated')},
                         {k: v for k, v in first.items() if k not in ('status', 'proposal_refs', 'updated')})
        self.assertIsNone(self.worker.run_once())
        self.assertEqual(self.agents.built, ['authoring'])
        self.assertEqual(self.agents.models.calls, calls)

    def test_the_same_request_id_with_another_command_is_a_conflict(self):
        self.job(self.queue('job-1'))
        self.refused(self.queue('job-1', self.evaluator(('Another requirement',))), 409, 'conflict')
        teacher = {**self.evaluator(), 'kind': 'generate-project-teacher'}
        self.refused(self.queue('job-1', teacher), 409, 'conflict')
        self.assertEqual(self.jobs.get(AUTH, 'job-1').command, self.evaluator())

    def test_queuing_needs_csrf_and_the_authority_to_propose(self):
        self.refused(self.queue('job-1', csrf=False), 403, 'forbidden')
        self.refused(self.queue('job-1', client=self.learner), 403, 'forbidden')
        self.install_policy('admin', without_action='propose')
        self.refused(self.queue('job-1'), 403, 'forbidden')
        self.assertIsNone(self.jobs.get(AUTH, 'job-1'))

    def test_an_unavailable_context_or_an_invalid_command_records_nothing(self):
        self.refused(self.queue('job-1', context_id='no-such-context'), 404, 'context_unavailable')
        invalid = {'kind': 'generate-project-assessments', 'command': {'requirements': ['Private draft text']}}
        detail = self.refused(self.queue('job-1', invalid), 422, 'validation')
        self.assertNotIn('Private draft text', json.dumps(detail))
        self.refused(self.queue('job-1', {'kind': 'generate-everything'}), 422, 'validation')
        self.refused(self.post(self.staff, f'/contexts/{AUTH}/jobs', {'job': self.evaluator()}), 422, 'validation')
        self.assertIsNone(self.jobs.get(AUTH, 'job-1'))

    def test_jobs_are_read_by_subjects_who_may_propose_in_the_context(self):
        self.job(self.queue('job-1'))
        self.refused(self.learner.get(f'/contexts/{AUTH}/jobs/job-1'), 403, 'forbidden')
        self.refused(self.staff.get(f'/contexts/{AUTH}/jobs/no-such-job'), 404, 'not_found')
        # A job belongs to its context: the same id elsewhere is another, unknown job.
        self.refused(self.staff.get(f'/contexts/{DELIVERY_TWO}/jobs/job-1'), 404, 'not_found')

    # Acceptance: an interrupted job can be abandoned by an administrator.
    def test_an_interrupted_job_is_abandoned_by_an_administrator(self):
        self.job(self.queue('job-1'))

        def interrupt(data):
            raise Interrupted()
        self.agents.models.callback = interrupt
        with self.assertRaises(Interrupted):
            self.worker.run_once()
        self.assertEqual(self.jobs.get(AUTH, 'job-1').status, 'RUNNING')
        path = f'/contexts/{AUTH}/jobs/job-1/abandonment'
        self.refused(self.post(self.staff, path, {}, csrf=False), 403, 'forbidden')
        self.refused(self.post(self.learner, path, {}), 403, 'forbidden')
        self.install_policy('admin', roles=['CONTENT_RESPONSIBLE', 'ASSESSOR'])
        self.refused(self.post(self.staff, path, {}), 422, 'validation')
        self.install_policy('admin', roles=['ADMINISTRATOR', 'CONTENT_RESPONSIBLE', 'ASSESSOR'])
        self.assertEqual(self.jobs.get(AUTH, 'job-1').status, 'RUNNING')

        abandoned = self.job(self.post(self.staff, path, {}), 'ABANDONED')
        self.assertEqual(abandoned['proposal_refs'], [])
        with LearningStore(self.location) as store:
            self.assertEqual(json.loads(store.request_record('job-1', AUTH).result)['content'], ABANDONED_CONTENT)
        self.refused(self.post(self.staff, path, {}), 409, 'conflict')
        self.assertEqual([StatusEvent.model_validate_json(e.data).status for e in self.jobs.events(AUTH, 'job-1')],
                         ['QUEUED', 'RUNNING', 'ABANDONED'])

    def test_a_queued_job_is_abandoned_before_the_worker_takes_it(self):
        self.job(self.queue('job-1'))
        path = f'/contexts/{AUTH}/jobs/job-1/abandonment'
        self.refused(self.post(self.learner, path, {}), 403, 'forbidden')
        self.install_policy('admin', roles=['CONTENT_RESPONSIBLE', 'ASSESSOR'])
        self.refused(self.post(self.staff, path, {}), 422, 'validation')
        self.install_policy('admin', roles=['ADMINISTRATOR', 'CONTENT_RESPONSIBLE', 'ASSESSOR'])
        self.assertEqual(self.jobs.get(AUTH, 'job-1').status, 'QUEUED')
        self.job(self.post(self.staff, path, {}), 'ABANDONED')
        self.assertIsNone(self.worker.run_once())
        with LearningStore(self.location) as store:
            self.assertIsNone(store.request_record('job-1', AUTH))
        self.assertEqual(self.agents.built, [])

    def test_a_job_that_has_ended_is_not_abandoned(self):
        self.job(self.queue('job-1'))
        self.worker.run_once()
        self.refused(self.post(self.staff, f'/contexts/{AUTH}/jobs/job-1/abandonment', {}), 409, 'conflict')
        self.assertEqual(self.jobs.get(AUTH, 'job-1').status, 'PROPOSED')

    def test_a_running_job_whose_request_is_not_reserved_yet_is_a_conflict(self):
        self.job(self.queue('job-1'))
        self.jobs.claim()
        self.refused(self.post(self.staff, f'/contexts/{AUTH}/jobs/job-1/abandonment', {}), 409, 'conflict')
        self.assertEqual(self.jobs.get(AUTH, 'job-1').status, 'RUNNING')

    # Acceptance: the event stream carries no content (strict event log in tests).
    def test_the_event_stream_follows_the_job_and_carries_no_content(self):
        self.job(self.queue('job-1'))
        self.worker.run_once()
        text = self.stream('job-1')
        events = parse_stream(text)
        self.assertEqual([name for _, name, _ in events], ['status', 'status', 'status'])
        self.assertEqual([StatusEvent.model_validate_json(data).status for _, _, data in events],
                         ['QUEUED', 'RUNNING', 'PROPOSED'])
        ids = [int(event_id) for event_id, _, _ in events]
        self.assertEqual(ids, sorted(set(ids)))
        for private in (REQUIREMENT, 'Submit a fictional business reminder prompt', 'clarity'):
            self.assertNotIn(private, text)
        # A reconnecting client continues after the last event it received.
        resumed = parse_stream(self.stream('job-1', **{'Last-Event-ID': str(ids[1])}))
        self.assertEqual(resumed, events[2:])
        # After the final event of an ended job there is nothing to wait for.
        waits = []
        self.app.state.job_wait = waits.append
        self.assertEqual(parse_stream(self.stream('job-1', **{'Last-Event-ID': str(ids[-1])})), [])
        self.assertEqual(waits, [])

    def test_the_stream_reports_progress_while_the_job_runs_and_ends_with_it(self):
        from tests.services.test_job_worker import emitting_kind
        from services.jobs.kinds import KINDS
        kind = emitting_kind({'type': 'worker.call', 'step_id': 's1', 'agent': 'Evaluator', 'status': 'ok'})
        self.worker.kinds = {**KINDS, kind.name: kind}
        self.jobs.submit(AUTH, 'job-1', 'admin', kind.name, {'kind': kind.name})
        waits = []
        self.app.state.job_wait = lambda seconds: waits.append(self.worker.run_once())
        events = parse_stream(self.stream('job-1'))
        self.assertEqual([name for _, name, _ in events], ['status', 'status', 'progress', 'status'])
        progress = Event.model_validate_json(events[2][2])
        self.assertEqual((progress.type, progress.request_id, progress.data['agent']), ('worker.call', 'job-1', 'Evaluator'))
        self.assertEqual(StatusEvent.model_validate_json(events[-1][2]).status, 'FAILED')
        self.assertEqual(len(waits), 1)

    def test_a_stream_ends_after_its_time_and_the_client_reconnects(self):
        self.job(self.queue('job-1'))
        self.app.state.job_stream_seconds = 0
        events = parse_stream(self.stream('job-1'))
        self.assertEqual([StatusEvent.model_validate_json(data).status for _, _, data in events], ['QUEUED'])

    def test_the_stream_is_authorized_before_it_starts(self):
        self.job(self.queue('job-1'))
        self.refused(self.learner.get(f'/contexts/{AUTH}/jobs/job-1/events'), 403, 'forbidden')
        self.refused(self.staff.get(f'/contexts/{AUTH}/jobs/no-such-job/events'), 404, 'not_found')


class JobsConfigurationTest(unittest.TestCase):
    def test_the_jobs_module_needs_a_jobs_store(self):
        from services.api_common.registry import ConfigurationError
        with TemporaryDirectory() as temp:
            root = Path(temp)
            seed = build_seed(root / 'seed', root / 'seed.sqlite')
            identities = write_identity_map(root, {'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'})
            settings = ApiSettings(auth=auth_settings(), identity_map=identities, store=str(root / 'seed.sqlite'),
                                   policy_dir=root / 'seed' / seed.policy_dir)
            with self.assertRaisesRegex(ConfigurationError, 'ALM_JOBS_STORE'):
                create_app(settings)
            create_app(settings.model_copy(update={'modules': ('review',)}))

    def test_settings_read_the_jobs_store_and_stream_timing_from_the_environment(self):
        env = {'ALM_OIDC_ISSUER': ISSUER, 'ALM_OIDC_CLIENT_ID': 'c', 'ALM_OIDC_CLIENT_SECRET': 's',
               'ALM_OIDC_REDIRECT_URI': 'https://testserver/auth/callback', 'ALM_IDENTITY_MAP': 'map.json'}
        defaults = ApiSettings.from_env(env)
        self.assertEqual((defaults.jobs_store, defaults.job_poll_seconds, defaults.job_stream_seconds), (None, 1.0, 300))
        settings = ApiSettings.from_env({**env, 'ALM_JOBS_STORE': 'jobs.sqlite', 'ALM_API_JOB_POLL_SECONDS': '0.5',
                                         'ALM_API_JOB_STREAM_SECONDS': '60'})
        self.assertEqual((settings.jobs_store.get_secret_value(), settings.job_poll_seconds, settings.job_stream_seconds),
                         ('jobs.sqlite', 0.5, 60))


if __name__ == '__main__':
    unittest.main()
