"""Agent job worker (S08): queued jobs run the existing service methods outside HTTP requests.

The worker claims the oldest queued job, opens its context with the trusted
policy (D10), runs the job kind's service method and records the outcome:
``PROPOSED`` with the pending proposal, ``REJECTED`` when the host refuses the
command, ``FAILED`` when generation does not complete, ``ABANDONED`` when an
administrator abandoned the request. Its content-free events go to the job's
event sink, recorded for the progress stream.
"""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
import unittest
from unittest.mock import Mock, patch

from agent_system import events
from learning.contracts import EntityRef, Record
from learning.metamodel import load_contract
from learning.outputs import LearningResponse
from learning.service import ABANDONED_CONTENT, LearningService
from learning.store import LearningStore
from services.jobs.kinds import KINDS, JobKind
from services.jobs.store import JobStore, StatusEvent
from services.jobs.worker import JobEventSink
from tests.authoring_cycle_fixtures import AUTH, trusted_policy
from tests.seed import build_seed
from tests.services.job_fixtures import (EXPORT, REQUIREMENT, SyntheticAgents, evaluator_command,
                                         evaluator_job, export_directory, new_jobs_location, worker)
from tests.store_backends import block_network, new_store_location, on_both_backends


NO_NETWORK = 'The job worker tests use synthetic models and no network'


class WorkerCase(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.location = new_store_location(self, temp.name, 'seed.sqlite')
        self.seed = build_seed(self.root / 'seed', self.location)
        self.policies = self.root / 'seed' / self.seed.policy_dir
        self.jobs = JobStore(new_jobs_location(self, temp.name))
        self.addCleanup(self.jobs.close)
        self.agents = SyntheticAgents(export_directory(self.root))
        self.worker = worker(self.location, self.policies, self.jobs, self.agents, strict_events=True)

    def submit(self, request_id, job, context_id=AUTH, subject='admin'):
        return self.jobs.submit(context_id, request_id, subject, job['kind'], job)[0]

    def statuses(self, request_id, context_id=AUTH):
        return [StatusEvent.model_validate_json(e.data).status
                for e in self.jobs.events(context_id, request_id) if e.name == 'status']

    def service(self, store):
        return LearningService(store, load_contract(), trusted_policy(), Mock())

    def pending(self):
        with LearningStore(self.location) as store:
            return [p.proposal.ref for p in self.service(store).pending_proposals(AUTH, 'admin')]

    def request_result(self, request_id, context_id=AUTH):
        with LearningStore(self.location) as store:
            row = store.request_record(request_id, context_id)
            return None if row is None else (row.result and json.loads(row.result))


@on_both_backends
class EvaluatorJobTest(WorkerCase):
    def test_a_queued_evaluator_job_ends_as_a_pending_proposal(self):
        self.submit('job-evaluator', evaluator_job(evaluator_command(self.location, self.seed.project)))
        before = self.pending()
        done = self.worker.run_once()
        self.assertEqual((done.request_id, done.status, done.detail), ('job-evaluator', 'PROPOSED', None))
        self.assertEqual(len(done.proposal_refs), 1)
        self.assertEqual(self.pending(), [done.proposal_refs[0], *before])
        self.assertEqual(self.jobs.get(AUTH, 'job-evaluator'), done)
        self.assertEqual(self.statuses('job-evaluator'), ['QUEUED', 'RUNNING', 'PROPOSED'])
        # The production service method ran with the exact command, once.
        self.assertEqual(self.agents.built, ['authoring'])
        self.assertEqual(self.agents.models.inputs[-1].command.requirements, (REQUIREMENT,))
        self.assertEqual(self.request_result('job-evaluator')['proposal_refs'],
                         [r.model_dump() for r in done.proposal_refs])
        self.assertIsNone(self.worker.run_once())

    def test_a_replayed_request_id_constructs_no_model(self):
        job = evaluator_job(evaluator_command(self.location, self.seed.project))
        first = self.submit('job-evaluator', job)
        done = self.worker.run_once()
        self.assertEqual(self.jobs.submit(AUTH, 'job-evaluator', 'admin', job['kind'], job), (done, False))
        self.assertNotEqual(first, done)
        self.assertIsNone(self.worker.run_once())
        self.assertEqual(self.agents.built, ['authoring'])

    def test_a_request_id_already_recorded_by_the_cli_replays_its_result_without_a_model(self):
        command = evaluator_command(self.location, self.seed.project)
        with LearningStore(self.location) as store:
            recorded = self.service(store).generate_project_assessments(AUTH, 'admin', command,
                request_id='cli-evaluator', authoring_factory=SyntheticAgents().authoring)
        self.submit('cli-evaluator', evaluator_job(command))
        done = self.worker.run_once()
        self.assertEqual((done.status, done.proposal_refs), ('PROPOSED', recorded.proposal_refs))
        self.assertEqual(self.agents.built, [])


@on_both_backends
class RefusedJobTest(WorkerCase):
    def test_a_stale_base_context_is_rejected_before_any_model(self):
        command = evaluator_command(self.location, self.seed.project)
        stale = command.model_copy(update={'base_context': EntityRef(type='ExecutionContext', id=AUTH, version='1')})
        self.submit('job-stale', evaluator_job(stale))
        done = self.worker.run_once()
        self.assertEqual(done.status, 'REJECTED')
        self.assertEqual(done.detail, 'Generation context is stale or foreign')
        self.assertEqual((done.proposal_refs, self.agents.built), ((), []))
        self.assertIsNone(self.request_result('job-stale'))

    def test_a_subject_without_authority_is_rejected(self):
        policy = self.policies / 'architecture-policy-1.json'
        data = json.loads(policy.read_text(encoding='utf-8'))
        data['subjects']['admin']['actions'][AUTH].remove('propose')
        policy.write_text(json.dumps(data), encoding='utf-8')
        for request_id, subject in (('job-admin', 'admin'), ('job-learner', 'learner')):
            self.submit(request_id, evaluator_job(evaluator_command(self.location, self.seed.project)), subject=subject)
            done = self.worker.run_once()
            with self.subTest(subject):
                self.assertEqual((done.status, done.detail), ('REJECTED', 'Action is not authorized'))
                self.assertIsNone(self.request_result(request_id))
        self.assertEqual(self.agents.built, [])

    def test_a_context_without_an_installed_policy_is_rejected(self):
        (self.policies / 'architecture-policy-1.json').unlink()
        self.submit('job-unavailable', evaluator_job(evaluator_command(self.location, self.seed.project)))
        done = self.worker.run_once()
        self.assertEqual((done.status, done.detail), ('REJECTED', 'Context unavailable'))
        self.assertEqual(self.agents.built, [])

    def test_an_invalid_recorded_command_is_rejected_without_echoing_it(self):
        self.submit('job-invalid', {'kind': 'generate-project-assessments', 'command': {'project': 'private text'}})
        done = self.worker.run_once()
        self.assertEqual((done.status, done.detail), ('REJECTED', 'Invalid job command'))
        self.assertEqual(self.agents.built, [])

    def test_an_unknown_kind_is_rejected(self):
        self.submit('job-unknown', {'kind': 'generate-everything'})
        self.assertEqual(self.worker.run_once().detail, 'Unknown job kind')

    def test_generation_that_does_not_complete_fails_without_a_proposal(self):
        self.agents.models.verdict = self.agents.models.verdict.model_copy(update={'verdict': 'REJECT'})
        before = self.pending()
        self.submit('job-failed', evaluator_job(evaluator_command(self.location, self.seed.project)))
        done = self.worker.run_once()
        self.assertEqual(done.status, 'FAILED')
        self.assertEqual(done.detail, 'Authoring generation did not complete; no accepted proposal was persisted.')
        self.assertEqual((done.proposal_refs, self.pending()), ((), before))
        self.assertEqual(self.request_result('job-failed')['kind'], 'FAILURE')

    def test_an_unexpected_error_fails_the_job_and_the_worker_goes_on(self):
        self.submit('job-broken', evaluator_job(evaluator_command(self.location, self.seed.project)))
        self.submit('job-next', {'kind': 'generate-everything'})
        with patch.object(LearningService, 'generate_project_assessments', side_effect=KeyError('private')):
            done = self.worker.run_once()
        self.assertEqual((done.status, done.detail), ('FAILED', 'Internal error'))
        self.assertEqual(self.worker.run_once().request_id, 'job-next')

    def test_a_job_abandoned_while_it_ran_stays_abandoned(self):
        self.submit('job-abandoned', evaluator_job(evaluator_command(self.location, self.seed.project)))

        def abandon(data):
            with LearningStore(self.location) as store:
                self.service(store).abandon_request(AUTH, 'admin', 'job-abandoned')
            self.jobs.transition(AUTH, 'job-abandoned', {'RUNNING'}, 'ABANDONED')
        self.agents.models.callback = abandon
        done = self.worker.run_once()
        self.assertEqual(done.status, 'ABANDONED')
        self.assertEqual(self.statuses('job-abandoned'), ['QUEUED', 'RUNNING', 'ABANDONED'])
        self.assertEqual(self.request_result('job-abandoned')['content'], ABANDONED_CONTENT)

    def test_an_abandoned_alm_request_ends_the_job_as_abandoned(self):
        self.submit('job-abandoned', evaluator_job(evaluator_command(self.location, self.seed.project)))

        def abandon(data):
            with LearningStore(self.location) as store:
                self.service(store).abandon_request(AUTH, 'admin', 'job-abandoned')
        self.agents.models.callback = abandon
        self.assertEqual(self.worker.run_once().status, 'ABANDONED')


@on_both_backends
class CuratorJobTest(WorkerCase):
    def syllabus_job(self, **changes):
        export = self.agents.exports / EXPORT
        job = {'kind': 'generate-aimpro-syllabus', 'project': {
            'name': EXPORT, 'sha256': hashlib.sha256(export.read_bytes()).hexdigest()},
            'source_scope': 'wp3', 'query': 'prompting', 'k': 3}
        job.update(changes)
        return job

    def test_a_curator_job_ends_as_a_pending_syllabus_proposal(self):
        export = (self.agents.exports / EXPORT).read_bytes()
        self.submit('job-curator', self.syllabus_job())
        done = self.worker.run_once()
        self.assertEqual(done.status, 'PROPOSED', done.detail)
        self.assertEqual(self.pending()[0], done.proposal_refs[0])
        self.assertEqual(self.agents.built, ['search', 'authoring'])
        self.assertEqual(self.agents.searches, [('prompting', 3)])
        self.assertEqual((self.agents.exports / EXPORT).read_bytes(), export)

    def test_an_export_that_differs_from_the_named_version_is_rejected(self):
        self.submit('job-curator', self.syllabus_job(project={'name': EXPORT, 'sha256': '0' * 64}))
        done = self.worker.run_once()
        self.assertEqual((done.status, self.agents.built), ('REJECTED', []))
        self.assertEqual(done.detail, 'The AIM-PRO export differs from the exact version named by the job')

    def test_a_missing_export_is_rejected(self):
        self.submit('job-curator', self.syllabus_job(project={'name': 'missing.json', 'sha256': '0' * 64}))
        self.assertEqual(self.worker.run_once().detail, 'The AIM-PRO export is not available to the worker')

    def test_a_worker_without_an_export_directory_rejects_curator_jobs(self):
        self.worker.resources = self.worker.resources._replace(exports=None)
        self.submit('job-curator', self.syllabus_job())
        self.assertEqual(self.worker.run_once().detail, 'The AIM-PRO export is not available to the worker')


class EmitCommand(Record):
    kind: Literal['emit-events']


def emitting_kind(*payloads):
    """A test kind that reports progress the way the orchestrator and the provider listener do."""

    def run(service, context_id, subject_key, request_id, command, resources):
        try:
            for payload in payloads:
                payload = dict(payload)
                events.emit(payload.pop('type'), **payload)
        except Exception:
            # As the service methods do: a run that does not complete is a failure response.
            return LearningResponse(kind='FAILURE', content='Synthetic job did not complete.')
        return LearningResponse(kind='FAILURE', content='Synthetic job finished.')
    return JobKind('emit-events', EmitCommand, run)


class EventSinkTest(WorkerCase):
    def run_kind(self, kind):
        self.worker.kinds = {**KINDS, kind.name: kind}
        self.submit('job-events', {'kind': kind.name})
        return self.worker.run_once()

    def test_the_run_events_reach_the_job_stream_in_order(self):
        done = self.run_kind(emitting_kind({'type': 'worker.call', 'step_id': 's1', 'agent': 'Evaluator', 'status': 'ok'},
                                           {'type': 'provider.call', 'model': 'synthetic', 'status': 'ok', 'duration_ms': 4}))
        self.assertEqual((done.status, done.detail), ('FAILED', 'Synthetic job finished.'))
        stream = self.jobs.events(AUTH, 'job-events')
        self.assertEqual([e.name for e in stream], ['status', 'status', 'progress', 'progress', 'status'])
        progress = [events.Event.model_validate_json(e.data) for e in stream if e.name == 'progress']
        self.assertEqual([(e.type, e.request_id, e.context_id, e.seq) for e in progress],
                         [('worker.call', 'job-events', AUTH, 0), ('provider.call', 'job-events', AUTH, 1)])
        self.assertEqual(len({e.run_id for e in progress}), 1)

    def test_a_content_event_is_refused_and_never_recorded(self):
        content = 'Private learner answer ' * 20
        done = self.run_kind(emitting_kind({'type': 'worker.call', 'step_id': 's1', 'status': 'ok'},
                                           {'type': 'worker.call', 'step_id': content}))
        # The strict log of the tests stops the run at the refused event.
        self.assertEqual((done.status, done.detail), ('FAILED', 'Synthetic job did not complete.'))
        recorded = ''.join(e.data for e in self.jobs.events(AUTH, 'job-events'))
        self.assertNotIn('Private learner answer', recorded)
        self.assertEqual([e.name for e in self.jobs.events(AUTH, 'job-events')],
                         ['status', 'status', 'progress', 'status'])

    def test_outside_tests_a_refused_event_is_dropped_and_the_job_goes_on(self):
        self.worker.strict_events = False
        done = self.run_kind(emitting_kind({'type': 'worker.call', 'step_id': 'x' * 500}))
        self.assertEqual((done.status, done.detail), ('FAILED', 'Synthetic job finished.'))
        self.assertEqual([e.name for e in self.jobs.events(AUTH, 'job-events')], ['status', 'status', 'status'])

    def test_the_sink_records_only_validated_events_of_its_job(self):
        self.submit('job-events', {'kind': 'emit-events'})
        job = self.jobs.claim()
        sink = JobEventSink(self.jobs, job, strict=True)
        with events.run(sink, request_id=job.request_id, context_id=job.context_id):
            events.emit('retrieval', step_id='s1', k=3)
        self.assertEqual([e.type for e in sink.events], ['retrieval'])
        self.assertEqual(len([e for e in self.jobs.events(AUTH, 'job-events') if e.name == 'progress']), 1)

    def test_events_outside_a_job_run_are_not_recorded(self):
        events.emit('retrieval', step_id='s1', k=3)
        self.assertEqual(self.jobs.events(AUTH, 'job-events'), ())


class KindsTest(unittest.TestCase):
    def test_one_kind_per_generator_and_curator_command_named_as_the_cli(self):
        from learning.__main__ import parse_args
        self.assertEqual(set(KINDS), {'generate-project-assessments', 'generate-project-teacher',
                                      'generate-project-trainer', 'generate-aimpro-syllabus'})
        base = ['--db', 'x', '--policy', 'p', '--subject', 's', '--context', 'c']
        for name in KINDS:
            with self.subTest(name):
                self.assertEqual(parse_args([*base, name, 'x', '--request-id', 'r', '--source-scope', 's',
                                             '--query', 'q'] if name == 'generate-aimpro-syllabus'
                                            else [*base, name, 'x', '--request-id', 'r']).command, name)

    def test_the_syllabus_command_needs_exactly_one_grounding(self):
        from services.jobs.kinds import SyllabusJob
        project = {'name': EXPORT, 'sha256': 'a' * 64}
        SyllabusJob(kind='generate-aimpro-syllabus', project=project, source_scope='wp3', query='q')
        SyllabusJob(kind='generate-aimpro-syllabus', project=project, source_scope='wp3', prepared_sources='r1')
        for grounding in ({}, {'query': 'q', 'prepared_sources': 'r1'}):
            with self.subTest(grounding), self.assertRaises(ValueError):
                SyllabusJob(kind='generate-aimpro-syllabus', project=project, source_scope='wp3', **grounding)

    def test_export_names_stay_inside_the_export_directory(self):
        from services.jobs.kinds import AimproExport
        for name in ('../alm.sqlite', 'sub/x.json', '.hidden.json', 'x.txt', ''):
            with self.subTest(name), self.assertRaises(ValueError):
                AimproExport(name=name, sha256='a' * 64)
        with self.assertRaises(ValueError):
            AimproExport(name=EXPORT, sha256='A' * 64)



if __name__ == '__main__':
    unittest.main()
