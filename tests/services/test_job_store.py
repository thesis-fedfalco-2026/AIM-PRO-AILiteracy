"""Jobs store (S08, D14): agent jobs and their events, apart from the ALM tables.

A job is named by its context and the ALM ``request_id`` of its command, the
idempotency key: submitting the same command again returns the same job, a
different command under the same id is a conflict. Status changes go one way
(``QUEUED`` → ``RUNNING`` → a final status, or ``ABANDONED``) and each one is
recorded as a ``status`` event, in the same transaction, next to the
``progress`` events of the run. A source preparation ends its run awaiting the
teacher's choice (S09a2, D22), which then moves it to ``ACCEPTED`` or
``DECLINED``, once.
"""

import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier, Thread
import unittest

from agent_system.events import Event
from learning.contracts import EntityRef
from learning.store import LearningStore, StateConflict
from services.jobs.store import CHOICES, ENDED, FINAL, JobStore, StatusEvent
from tests.store_backends import block_network, on_both_backends
from tests.services.job_fixtures import new_jobs_location


COMMAND = {'kind': 'generate-project-assessments', 'command': {'requirements': ['Synthetic requirement']}}
PROPOSAL = EntityRef(type='ChangeProposal', id='synthetic-proposal', version='1')


def progress(seq=0, **data):
    return Event(event_id=f'event-{seq}', run_id='run', seq=seq, time='2026-11-09T00:00:00.000+00:00',
                 type='worker.call', request_id='r1', context_id='c1', data=data or {'status': 'ok'})


@on_both_backends
class JobStoreTest(unittest.TestCase):
    def setUp(self):
        block_network(self, 'The jobs store needs no network')
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = temp.name
        self.location = new_jobs_location(self, temp.name)
        self.jobs = JobStore(self.location)
        self.addCleanup(self.jobs.close)

    def submit(self, request_id='r1', context_id='c1', subject='admin', command=COMMAND):
        return self.jobs.submit(context_id, request_id, subject, command['kind'], command)

    def statuses(self, context_id='c1', request_id='r1'):
        return [StatusEvent.model_validate_json(e.data).status
                for e in self.jobs.events(context_id, request_id) if e.name == 'status']

    def test_a_submitted_job_is_queued_with_its_exact_command(self):
        job, created = self.submit()
        self.assertTrue(created)
        self.assertEqual((job.context_id, job.request_id, job.subject_key, job.kind, job.status),
                         ('c1', 'r1', 'admin', 'generate-project-assessments', 'QUEUED'))
        self.assertEqual(job.command, COMMAND)
        self.assertEqual((job.proposal_refs, job.detail), ((), None))
        self.assertEqual(self.jobs.get('c1', 'r1'), job)
        self.assertIsNone(self.jobs.get('c1', 'other'))
        self.assertIsNone(self.jobs.get('c2', 'r1'))
        self.assertEqual(self.statuses(), ['QUEUED'])

    def test_a_replayed_request_id_returns_the_same_job(self):
        job, _ = self.submit()
        again, created = self.submit()
        self.assertFalse(created)
        self.assertEqual(again, job)
        self.assertEqual(self.statuses(), ['QUEUED'])

    def test_the_same_request_id_with_another_command_or_subject_is_a_conflict(self):
        job, _ = self.submit()
        other = {**COMMAND, 'command': {'requirements': ['Another requirement']}}
        for kwargs in ({'command': other}, {'subject': 'someone-else'},
                       {'command': {**COMMAND, 'kind': 'generate-project-teacher'}}):
            with self.subTest(kwargs), self.assertRaises(StateConflict):
                self.submit(**kwargs)
        self.assertEqual(self.jobs.get('c1', 'r1'), job)
        # The same id in another context is another job, as ALM request ids are per context.
        self.assertTrue(self.submit(context_id='c2')[1])

    def test_concurrent_identical_submissions_record_one_job(self):
        barrier, results, errors = Barrier(4), [], []

        def submit():
            with JobStore(self.location) as jobs:
                barrier.wait()
                try:
                    results.append(jobs.submit('c1', 'r1', 'admin', COMMAND['kind'], COMMAND))
                except Exception as error:  # pragma: no cover - reported below
                    errors.append(error)

        threads = [Thread(target=submit) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(len({job.model_dump_json() for job, _ in results}), 1)
        self.assertEqual(self.statuses(), ['QUEUED'])

    def test_the_worker_claims_the_oldest_queued_job_once(self):
        self.submit('r1')
        self.submit('r2')
        first = self.jobs.claim()
        self.assertEqual((first.request_id, first.status), ('r1', 'RUNNING'))
        self.assertEqual(self.jobs.claim().request_id, 'r2')
        self.assertIsNone(self.jobs.claim())
        self.assertEqual(self.statuses(), ['QUEUED', 'RUNNING'])

    def test_concurrent_claims_never_take_the_same_job(self):
        for index in range(6):
            self.submit(f'r{index}')
        barrier, claimed = Barrier(3), []

        def claim():
            with JobStore(self.location) as jobs:
                barrier.wait()
                while (job := jobs.claim()) is not None:
                    claimed.append(job.request_id)

        threads = [Thread(target=claim) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(claimed), [f'r{index}' for index in range(6)])

    def test_a_running_job_ends_once_with_its_outcome(self):
        self.submit()
        self.jobs.claim()
        done = self.jobs.transition('c1', 'r1', {'RUNNING'}, 'PROPOSED', proposal_refs=(PROPOSAL,))
        self.assertEqual((done.status, done.proposal_refs, done.detail), ('PROPOSED', (PROPOSAL,), None))
        self.assertIsNone(self.jobs.transition('c1', 'r1', {'RUNNING'}, 'FAILED', detail='Too late'))
        self.assertEqual(self.jobs.get('c1', 'r1'), done)
        events = [e for e in self.jobs.events('c1', 'r1') if e.name == 'status']
        self.assertEqual(StatusEvent.model_validate_json(events[-1].data),
                         StatusEvent(status='PROPOSED', proposal_refs=(PROPOSAL,)))

    def test_final_statuses_never_change(self):
        self.assertEqual(FINAL, {'PROPOSED', 'REJECTED', 'FAILED', 'ABANDONED', 'COMPLETED', 'ACCEPTED', 'DECLINED'})
        self.assertEqual(ENDED, FINAL | {'AWAITING_CHOICE'})
        for index, status in enumerate(sorted(FINAL)):
            request_id = f'r{index}'
            self.submit(request_id)
            self.jobs.transition('c1', request_id, {'QUEUED'}, 'RUNNING')
            if status in CHOICES:
                self.jobs.transition('c1', request_id, {'RUNNING'}, 'AWAITING_CHOICE')
                self.jobs.transition('c1', request_id, {'AWAITING_CHOICE'}, status)
            else:
                self.jobs.transition('c1', request_id, {'RUNNING'}, status)
            for current, target in [*((({'QUEUED', 'RUNNING'}, t) for t in ('RUNNING', 'AWAITING_CHOICE', *FINAL)
                                          if t not in CHOICES)),
                                    *(({'AWAITING_CHOICE'}, t) for t in CHOICES)]:
                with self.subTest(status=status, target=target):
                    self.assertIsNone(self.jobs.transition('c1', request_id, current, target))
            self.assertEqual(self.jobs.get('c1', request_id).status, status)

    def test_a_run_awaiting_the_choice_is_accepted_or_declined_once(self):
        for request_id, choice in (('r1', 'ACCEPTED'), ('r2', 'DECLINED')):
            self.submit(request_id)
            self.jobs.claim()
            waiting = self.jobs.transition('c1', request_id, {'RUNNING'}, 'AWAITING_CHOICE')
            self.assertEqual((waiting.status, waiting.proposal_refs, waiting.detail), ('AWAITING_CHOICE', (), None))
            # The run has ended: it is never claimed or ended again by a worker.
            self.assertIsNone(self.jobs.claim())
            self.assertIsNone(self.jobs.transition('c1', request_id, {'QUEUED', 'RUNNING'}, 'ABANDONED'))
            chosen = self.jobs.transition('c1', request_id, {'AWAITING_CHOICE'}, choice)
            self.assertEqual(chosen.status, choice)
            for other in ('ACCEPTED', 'DECLINED'):
                with self.subTest(choice=choice, other=other):
                    self.assertIsNone(self.jobs.transition('c1', request_id, {'AWAITING_CHOICE'}, other))
            self.assertEqual(self.statuses(request_id=request_id), ['QUEUED', 'RUNNING', 'AWAITING_CHOICE', choice])

    def test_the_jobs_of_a_context_are_listed_newest_first(self):
        for request_id in ('r1', 'r2', 'r3'):
            self.submit(request_id)
        self.submit('r4', context_id='c2')
        self.jobs.claim()
        listed = self.jobs.list('c1')
        self.assertEqual([j.request_id for j in listed], ['r3', 'r2', 'r1'])
        self.assertEqual(listed[2], self.jobs.get('c1', 'r1'))
        self.assertEqual([j.request_id for j in self.jobs.list('c1', limit=2)], ['r3', 'r2'])
        self.assertEqual(self.jobs.list('c3'), ())
        with self.assertRaises(ValueError):
            self.jobs.list('c1', limit=0)

    def test_a_transition_refuses_unknown_statuses_and_jobs(self):
        self.submit()
        with self.assertRaises(ValueError):
            self.jobs.transition('c1', 'r1', {'QUEUED'}, 'DONE')
        with self.assertRaises(ValueError):
            self.jobs.transition('c1', 'r1', {'QUEUED'}, 'QUEUED')
        # Only the teacher's choice ends a run awaiting it, and nothing else is a choice.
        for current, status in (({'RUNNING'}, 'ACCEPTED'), ({'QUEUED', 'RUNNING'}, 'DECLINED'),
                                ({'AWAITING_CHOICE'}, 'PROPOSED'), ({'AWAITING_CHOICE'}, 'ABANDONED'),
                                ({'AWAITING_CHOICE', 'RUNNING'}, 'ACCEPTED')):
            with self.subTest(current=current, status=status), self.assertRaises(ValueError):
                self.jobs.transition('c1', 'r1', current, status)
        self.assertIsNone(self.jobs.transition('c1', 'missing', {'QUEUED'}, 'ABANDONED'))

    def test_a_queued_job_can_be_abandoned_and_is_never_claimed(self):
        self.submit()
        self.assertEqual(self.jobs.transition('c1', 'r1', {'QUEUED'}, 'ABANDONED').status, 'ABANDONED')
        self.assertIsNone(self.jobs.claim())
        self.assertEqual(self.statuses(), ['QUEUED', 'ABANDONED'])

    def test_progress_events_are_recorded_in_order_after_a_cursor(self):
        self.submit()
        self.submit('r2')
        self.jobs.claim()
        self.jobs.add_progress('c1', 'r1', progress(0))
        self.jobs.add_progress('c1', 'r2', progress(0, status='other job'))
        self.jobs.add_progress('c1', 'r1', progress(1, status='error'))
        events = self.jobs.events('c1', 'r1')
        self.assertEqual([e.name for e in events], ['status', 'status', 'progress', 'progress'])
        self.assertEqual([e.seq for e in events], sorted(e.seq for e in events))
        self.assertEqual(Event.model_validate_json(events[2].data), progress(0))
        self.assertEqual(json.loads(events[3].data)['data'], {'status': 'error'})
        self.assertEqual(self.jobs.events('c1', 'r1', after=events[1].seq), events[2:])
        self.assertEqual(self.jobs.events('c1', 'missing'), ())
        with self.assertRaises(ValueError):
            self.jobs.add_progress('c1', 'missing', progress(2))

    def test_the_store_reopens_with_its_records(self):
        job, _ = self.submit()
        self.jobs.close()
        with JobStore(self.location) as reopened:
            self.assertEqual(reopened.get('c1', 'r1'), job)


class JobStoreSqliteTest(unittest.TestCase):
    def test_the_jobs_store_is_never_the_alm_database(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'alm.sqlite'
            LearningStore(path).close()
            with self.assertRaisesRegex(ValueError, 'ALM'):
                JobStore(path)
            with LearningStore(path) as store:
                self.assertEqual(store.table_digests()['requests'].rows, 0)

    def test_a_jobs_database_of_another_version_is_refused(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'jobs.sqlite'
            JobStore(path).close()
            connection = sqlite3.connect(path)
            connection.execute('PRAGMA user_version=99')
            connection.close()
            with self.assertRaisesRegex(ValueError, 'version'):
                JobStore(path)


if __name__ == '__main__':
    unittest.main()
