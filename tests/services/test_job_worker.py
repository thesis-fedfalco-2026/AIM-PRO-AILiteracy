"""Agent job worker (S08): queued jobs run the existing service methods outside HTTP requests.

The worker claims the oldest queued job, opens its context with the trusted
policy (D10), runs the job kind's service method and records the outcome:
``PROPOSED`` with the pending proposal, ``REJECTED`` when the host refuses the
command, ``FAILED`` when generation does not complete, ``ABANDONED`` when an
administrator abandoned the request. Source jobs (S09a2) propose nothing: a
discovery is ``COMPLETED``, a preparation is ``AWAITING_CHOICE`` until the
teacher accepts or declines it, and a Curator job never uses prepared sources
that were not accepted. A revision job (S09b) asks the Curator to revise a
syllabus proposal after the teacher's revision request, on the same sources.
Its content-free events go to the job's event sink, recorded for the progress
stream.
"""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
import unittest
from unittest.mock import Mock, patch

from agent_system import events
from aimpro.generators import NOT_ACCEPTED as GENERATION_NOT_ACCEPTED
from aimpro.syllabus_refinement import NO_REQUEST
from aimpro.syllabus_state import NOT_ACCEPTED
from learning.contracts import EntityRef, Record
from learning.metamodel import load_contract
from learning.outputs import LearningResponse
from learning.service import ABANDONED_CONTENT, LearningService
from learning.store import LearningStore
from services.jobs.kinds import KINDS, JobKind
from services.jobs.store import JobStore, StatusEvent
from services.jobs.worker import JobEventSink
from tests.authoring_cycle_fixtures import AUTH, trusted_policy
from tests.generator_fixtures import GENERATION_REJECTION
from tests.seed import build_seed
from tests.services.job_fixtures import (EXPORT, REQUIREMENT, SyntheticAgents, discovery_job, evaluator_command,
                                         evaluator_job, export_directory, export_ref, new_jobs_location,
                                         prepared_syllabus_job, preparation_job, revision_job, source_plan,
                                         worker)
from tests.store_backends import block_network, new_store_location, on_both_backends
from tests.syllabus_fixtures import REJECTION


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

    def test_generation_the_review_agent_never_accepts_is_proposed_with_the_notice_as_detail(self):
        # Owner decision of 13 November 2026 (S09d): a flow ends with something for the teacher to decide.
        self.agents.models.verdict = GENERATION_REJECTION
        self.submit('job-not-accepted', evaluator_job(evaluator_command(self.location, self.seed.project)))
        done = self.worker.run_once()
        self.assertEqual((done.status, done.detail), ('PROPOSED', GENERATION_NOT_ACCEPTED))
        result = self.request_result('job-not-accepted')
        # S09c (D30): every draft's verdict is kept with the result; the events carry no reason.
        self.assertEqual([a['review'] for a in result['attempts']], [GENERATION_REJECTION.model_dump(mode='json')] * 4)
        reviews = [json.loads(e.data)['data'] for e in self.jobs.events(AUTH, 'job-not-accepted')
                   if e.name == 'progress' and json.loads(e.data)['type'] == 'review']
        self.assertEqual([(r['stage'], r['attempt'], r['verdict']) for r in reviews],
                         [('PROJECT', n, 'REJECT') for n in (1, 2, 3)] + [('PROJECT_FINAL', 1, 'REJECT')])
        stored = json.dumps([e.data for e in self.jobs.events(AUTH, 'job-not-accepted')]) + done.model_dump_json()
        self.assertNotIn(GENERATION_REJECTION.reason, stored)

    def test_generation_that_does_not_complete_fails_without_a_proposal(self):
        self.agents.models.transform = lambda data, draft: draft.model_copy(update={'input_digest': 'invented'})
        before = self.pending()
        self.submit('job-failed', evaluator_job(evaluator_command(self.location, self.seed.project)))
        done = self.worker.run_once()
        self.assertEqual(done.status, 'FAILED')
        self.assertEqual(done.detail, 'Authoring generation did not complete (Generated output does not identify the '
                                      'exact host input snapshot); no accepted proposal was persisted.')
        self.assertEqual((done.proposal_refs, self.pending()), ((), before))
        self.assertEqual([a['check'] for a in self.request_result('job-failed')['attempts']],
                         ['Generated output does not identify the exact host input snapshot'] * 3)

    def test_a_draft_refused_once_is_proposed_on_the_next_attempt(self):
        self.agents.models.verdicts.append(GENERATION_REJECTION)
        self.submit('job-retried', evaluator_job(evaluator_command(self.location, self.seed.project)))
        done = self.worker.run_once()
        self.assertEqual(done.status, 'PROPOSED', done.detail)
        self.assertEqual([(a['attempt'], a.get('block'), a.get('final', False))
                          for a in self.request_result('job-retried')['attempts']], [(1, 1, False), (2, 1, False), (1, None, True)])

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

    def test_a_syllabus_rejected_at_every_attempt_is_proposed_with_the_notice_and_the_verdicts_kept(self):
        # Owner decision (issue #112): the teacher decides on the last checked draft, told it was not accepted.
        self.agents.reviewer.value = REJECTION
        self.submit('job-curator', self.syllabus_job())
        done = self.worker.run_once()
        self.assertEqual((done.status, done.detail), ('PROPOSED', NOT_ACCEPTED))
        self.assertEqual(self.pending()[0], done.proposal_refs[0])
        self.assertEqual([a['review'] for a in self.request_result('job-curator')['attempts']],
                         [REJECTION.model_dump(mode='json')] * 3)
        reviews = [json.loads(e.data)['data'] for e in self.jobs.events(AUTH, 'job-curator')
                   if e.name == 'progress' and json.loads(e.data)['type'] == 'review']
        self.assertEqual([(r['attempt'], r['verdict']) for r in reviews], [(1, 'REJECT'), (2, 'REJECT'), (3, 'REJECT')])
        stored = json.dumps([e.data for e in self.jobs.events(AUTH, 'job-curator')]) + done.model_dump_json()
        self.assertNotIn(REJECTION.reason, stored)
        self.assertEqual(self.agents.built, ['search', 'authoring'])

    def test_a_syllabus_rejected_once_is_proposed_on_the_next_attempt(self):
        self.agents.reviewer.queue.append(REJECTION)
        self.submit('job-curator', self.syllabus_job())
        done = self.worker.run_once()
        self.assertEqual(done.status, 'PROPOSED', done.detail)
        self.assertEqual([a['attempt'] for a in self.request_result('job-curator')['attempts']], [1, 2])

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


@on_both_backends
class SourceJobTest(WorkerCase):
    NOT_ACCEPTED = 'The prepared sources have not been accepted by the teacher'

    def setUp(self):
        super().setUp()
        self.export = export_ref(self.agents.exports)

    def prepare(self, request_id='job-sources', subject='admin'):
        self.submit(request_id, preparation_job(self.export), subject=subject)
        return self.worker.run_once()

    def test_a_discovery_job_completes_with_the_excerpts_found_and_no_proposal(self):
        before = self.pending()
        self.submit('job-discovery', discovery_job('prompting', 'prompt clarity'))
        done = self.worker.run_once()
        self.assertEqual((done.status, done.proposal_refs, done.detail), ('COMPLETED', (), None))
        self.assertEqual(self.statuses('job-discovery'), ['QUEUED', 'RUNNING', 'COMPLETED'])
        self.assertEqual(self.agents.built, ['search-client'])
        self.assertEqual(self.agents.searches, [('prompting', 3), ('prompt clarity', 3)])
        self.assertEqual(self.request_result('job-discovery')['kind'], 'SOURCE_DISCOVERY')
        self.assertEqual(self.pending(), before)

    def test_a_preparation_job_awaits_the_teachers_choice(self):
        before = self.pending()
        export = (self.agents.exports / EXPORT).read_bytes()
        done = self.prepare()
        self.assertEqual((done.status, done.proposal_refs, done.detail), ('AWAITING_CHOICE', (), None))
        self.assertEqual(self.statuses('job-sources'), ['QUEUED', 'RUNNING', 'AWAITING_CHOICE'])
        self.assertEqual(self.agents.built, ['search-client'])
        self.assertEqual(self.agents.fetches, [('chunk-1',)])
        self.assertEqual(self.request_result('job-sources')['kind'], 'SOURCE_PREPARATION')
        self.assertEqual(self.pending(), before)
        self.assertEqual((self.agents.exports / EXPORT).read_bytes(), export)

    # Acceptance: a replayed request id returns the same preparation and runs no retrieval again.
    def test_a_preparation_already_recorded_under_the_request_id_runs_no_retrieval(self):
        with LearningStore(self.location) as store:
            recorded = self.service(store).prepare_aimpro_syllabus_sources(AUTH, 'admin',
                self.agents.exports / EXPORT, source_plan(self.export), request_id='cli-sources',
                search_client_factory=SyntheticAgents().search_client)
        done = self.prepare('cli-sources')
        self.assertEqual(done.status, 'AWAITING_CHOICE')
        self.assertEqual((self.agents.built, self.agents.searches, self.agents.fetches), ([], [], []))
        self.assertEqual(self.request_result('cli-sources'), recorded.model_dump(mode='json'))

    # Acceptance: sources that were not accepted are never used by a Curator job.
    def test_a_curator_job_never_uses_prepared_sources_that_were_not_accepted(self):
        self.prepare('job-waiting')
        self.prepare('job-declined')
        self.jobs.transition(AUTH, 'job-declined', {'AWAITING_CHOICE'}, 'DECLINED')
        with LearningStore(self.location) as store:
            self.service(store).prepare_aimpro_syllabus_sources(AUTH, 'admin', self.agents.exports / EXPORT,
                source_plan(self.export), request_id='cli-sources', search_client_factory=SyntheticAgents().search_client)
        self.submit('job-discovery', discovery_job())
        self.worker.run_once()
        self.agents.built.clear()
        before = self.pending()
        for index, prepared in enumerate(('job-waiting', 'job-declined', 'cli-sources', 'job-discovery', 'missing')):
            request_id = f'job-curator-{index}'
            self.submit(request_id, prepared_syllabus_job(self.export, prepared))
            done = self.worker.run_once()
            with self.subTest(prepared=prepared):
                self.assertEqual((done.status, done.detail), ('REJECTED', self.NOT_ACCEPTED))
                self.assertIsNone(self.request_result(request_id))
        self.assertEqual((self.agents.built, self.pending()), ([], before))

    def test_sources_accepted_by_another_subject_are_not_used(self):
        # A preparation job of another subject, driven to ACCEPTED by hand, names a request the admin made.
        with LearningStore(self.location) as store:
            self.service(store).prepare_aimpro_syllabus_sources(AUTH, 'admin', self.agents.exports / EXPORT,
                source_plan(self.export), request_id='job-sources', search_client_factory=SyntheticAgents().search_client)
        self.submit('job-sources', preparation_job(self.export), subject='someone-else')
        self.jobs.claim()
        self.jobs.transition(AUTH, 'job-sources', {'RUNNING'}, 'AWAITING_CHOICE')
        self.jobs.transition(AUTH, 'job-sources', {'AWAITING_CHOICE'}, 'ACCEPTED')
        self.submit('job-curator', prepared_syllabus_job(self.export, 'job-sources'))
        done = self.worker.run_once()
        self.assertEqual((done.status, done.detail), ('REJECTED', self.NOT_ACCEPTED))
        self.assertIsNone(self.request_result('job-curator'))

    def test_a_curator_job_on_accepted_sources_proposes_a_syllabus_without_a_new_search(self):
        self.prepare()
        self.jobs.transition(AUTH, 'job-sources', {'AWAITING_CHOICE'}, 'ACCEPTED')
        searches = list(self.agents.searches)
        self.agents.built.clear()
        self.submit('job-curator', prepared_syllabus_job(self.export, 'job-sources'))
        done = self.worker.run_once()
        self.assertEqual(done.status, 'PROPOSED', done.detail)
        self.assertEqual(self.pending()[0], done.proposal_refs[0])
        self.assertEqual(self.agents.built, ['authoring'])
        self.assertEqual(self.agents.searches, searches)

    def test_a_worker_without_a_search_client_rejects_source_jobs(self):
        self.worker.resources = self.worker.resources._replace(search_client=None)
        self.submit('job-discovery', discovery_job())
        self.assertEqual(self.worker.run_once().detail, 'Source retrieval is not available to the worker')


@on_both_backends
class RevisionJobTest(WorkerCase):
    REASON = 'Add a unit where participants explain two choices.'

    def setUp(self):
        super().setUp()
        self.export = export_ref(self.agents.exports)

    def proposed(self, job, request_id='job-curator'):
        self.submit(request_id, job)
        done = self.worker.run_once()
        self.assertEqual(done.status, 'PROPOSED', done.detail)
        return done.proposal_refs[0]

    def request_revision(self, proposal):
        with LearningStore(self.location) as store:
            self.service(store).decide(AUTH, 'admin', proposal, 'REQUEST_REVISION', self.REASON)

    def test_a_revision_job_gives_the_reason_to_the_curator_and_proposes_a_revised_syllabus(self):
        first = self.proposed({'kind': 'generate-aimpro-syllabus', 'project': self.export,
                               'source_scope': 'wp3', 'query': 'prompting', 'k': 3})
        self.request_revision(first)
        before = self.pending()
        self.assertNotIn(first, before)
        searches = list(self.agents.searches)
        self.agents.built.clear()
        second = self.proposed(revision_job(first.id), 'job-revision')
        self.assertEqual(self.pending(), [second, *before])
        self.assertEqual(self.agents.built, ['authoring'])
        self.assertEqual(self.agents.searches, searches)
        prompt = self.agents.curator.calls[-1][1]
        self.assertEqual(json.loads(prompt.split('\nDATA\n')[1])['teacher_reasons'], [self.REASON])

    def test_a_revision_without_a_revision_request_is_rejected_before_any_model(self):
        first = self.proposed({'kind': 'generate-aimpro-syllabus', 'project': self.export,
                               'source_scope': 'wp3', 'query': 'prompting', 'k': 3})
        self.agents.built.clear()
        self.submit('job-revision', revision_job(first.id))
        done = self.worker.run_once()
        self.assertEqual((done.status, self.agents.built), ('REJECTED', []))
        self.assertEqual(done.detail, NO_REQUEST)
        self.submit('job-unknown', revision_job('proposal-unknown'))
        self.assertEqual(self.worker.run_once().detail, 'Unknown syllabus proposal')

    # Owner decision 4: a revision on prepared sources reuses the accepted preparation.
    def test_a_revision_on_accepted_sources_reuses_them_without_a_new_retrieval(self):
        self.submit('job-sources', preparation_job(self.export))
        self.worker.run_once()
        self.jobs.transition(AUTH, 'job-sources', {'AWAITING_CHOICE'}, 'ACCEPTED')
        first = self.proposed(prepared_syllabus_job(self.export, 'job-sources'))
        self.request_revision(first)
        retrieval = (list(self.agents.searches), list(self.agents.fetches))
        self.agents.built.clear()
        self.proposed(revision_job(first.id), 'job-revision')
        self.assertEqual(self.agents.built, ['authoring'])
        self.assertEqual((self.agents.searches, self.agents.fetches), retrieval)


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
                                      'generate-project-trainer', 'generate-aimpro-syllabus',
                                      'discover-aimpro-syllabus-sources', 'prepare-aimpro-syllabus-sources',
                                      'revise-aimpro-syllabus'})
        base = ['--db', 'x', '--policy', 'p', '--subject', 's', '--context', 'c']
        arguments = {'generate-aimpro-syllabus': ['x', '--source-scope', 's', '--query', 'q'],
                     'discover-aimpro-syllabus-sources': ['--discovery', 'd'],
                     'prepare-aimpro-syllabus-sources': ['x', '--plan', 'p'],
                     'revise-aimpro-syllabus': ['--proposal', 'p']}
        for name in KINDS:
            with self.subTest(name):
                self.assertEqual(parse_args([*base, name, *arguments.get(name, ['x']), '--request-id', 'r']).command,
                                 name)

    def test_a_preparation_names_the_export_its_plan_was_written_for(self):
        from services.jobs.kinds import PreparationJob
        export = {'name': EXPORT, 'sha256': 'a' * 64}
        PreparationJob.model_validate(preparation_job(export))
        with self.assertRaises(ValueError):
            PreparationJob.model_validate({**preparation_job(export), 'project': {'name': EXPORT, 'sha256': 'b' * 64}})

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
