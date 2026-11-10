"""The agent job worker: queued jobs run the existing service methods outside HTTP requests.

The worker claims the oldest queued job, opens its context with the trusted
policy (D10), checks again that the job's subject may propose there, and runs
the job kind inside an ``agent_system.events`` run bound to the job's event
sink. The outcome is recorded once:

- ``PROPOSED``: the service recorded a pending proposal, linked from the job;
- ``COMPLETED``: a source discovery recorded the excerpts it found (no proposal);
- ``AWAITING_CHOICE``: a source preparation recorded its exact excerpts, which
  the teacher accepts or declines (no proposal);
- ``REJECTED``: the host refused the command before any model (stale base,
  authority, missing or changed export, invalid command); ``detail`` is the
  core's fixed message, never input text; a Curator job naming prepared
  sources that the teacher has not accepted is refused here;
- ``FAILED``: generation did not complete, or an unexpected error;
- ``ABANDONED``: an administrator abandoned the request while it ran.
"""

from __future__ import annotations

import logging
from threading import Event as Signal, Lock

from pydantic import ValidationError

from agent_system import events
from learning.policies import AuthorizationError
from learning.service import ABANDONED_CONTENT
from services.api_common.errors import ContextUnavailable
from services.jobs.kinds import KINDS, unaccepted_sources
from services.jobs.store import JobRecord


logger = logging.getLogger('services.jobs')


class JobEventSink:
    """The content-free events of one job's run, kept in memory and recorded for the progress stream.

    ``events.emit`` validates an event before it reaches a log, so an event
    carrying content never gets here: a strict sink (tests) makes it fail the
    run, otherwise it is dropped with a warning. The API runs in another
    process, so each event is also recorded in the jobs store, which the API
    streams from.
    """

    def __init__(self, jobs, job: JobRecord, *, strict: bool = False):
        self.jobs, self.job, self.strict = jobs, job, strict
        self.events: list[events.Event] = []
        self._lock = Lock()

    def append(self, event: events.Event) -> None:
        with self._lock:
            self.events.append(event)
        self.jobs.add_progress(self.job.context_id, self.job.request_id, event)


def outcome(response) -> tuple[str, tuple, str | None]:
    """The job status, proposal references and detail of a service response."""
    if response.kind == 'PROPOSAL' and response.proposal_refs:
        return 'PROPOSED', tuple(response.proposal_refs), None
    if response.kind == 'SOURCE_DISCOVERY':
        return 'COMPLETED', (), None
    if response.kind == 'SOURCE_PREPARATION':
        return 'AWAITING_CHOICE', (), None
    if response.kind == 'FAILURE':
        if response.content == ABANDONED_CONTENT:
            return 'ABANDONED', (), None
        return 'FAILED', (), response.content
    return 'FAILED', (), 'Unexpected response'


class Worker:
    def __init__(self, jobs, contexts, resources, *, kinds=KINDS, strict_events: bool = False):
        self.jobs, self.contexts, self.resources = jobs, contexts, resources
        self.kinds, self.strict_events = kinds, strict_events

    def run_once(self) -> JobRecord | None:
        """Run the oldest queued job to its outcome; ``None`` when no job waits."""
        job = self.jobs.claim()
        if job is None:
            return None
        status, proposal_refs, detail = self._run(job)
        done = self.jobs.transition(job.context_id, job.request_id, {'RUNNING'}, status,
                                    proposal_refs=proposal_refs, detail=detail)
        # ``None``: an administrator abandoned the job while it ran; that status stays.
        return done or self.jobs.get(job.context_id, job.request_id)

    def run(self, stop: Signal, poll_seconds: float = 1.0) -> None:
        while not stop.is_set():
            if self.run_once() is None:
                stop.wait(poll_seconds)

    def _run(self, job: JobRecord) -> tuple[str, tuple, str | None]:
        kind = self.kinds.get(job.kind)
        if kind is None:
            return 'REJECTED', (), 'Unknown job kind'
        try:
            command = kind.command.model_validate(job.command)
        except ValidationError:
            return 'REJECTED', (), 'Invalid job command'
        sink = JobEventSink(self.jobs, job, strict=self.strict_events)
        try:
            with self.contexts.open(job.context_id) as service:
                service.authorize_jobs(job.context_id, job.subject_key)
                refused = unaccepted_sources(self.jobs, job.context_id, job.subject_key, command)
                if refused is not None:
                    return 'REJECTED', (), refused
                with events.run(sink, request_id=job.request_id, context_id=job.context_id):
                    response = kind.run(service, job.context_id, job.subject_key, job.request_id, command,
                                        self.resources)
        except ContextUnavailable:
            return 'REJECTED', (), 'Context unavailable'
        except AuthorizationError:
            return 'REJECTED', (), 'Action is not authorized'
        except ValidationError:
            return 'REJECTED', (), 'Invalid job command'
        except ValueError as error:
            # Host checks before any model, StateConflict included: their messages are fixed texts.
            return 'REJECTED', (), str(error)
        except Exception as error:
            logger.error('Job %s did not complete (%s)', job.request_id, type(error).__name__)
            return 'FAILED', (), 'Internal error'
        return outcome(response)
