"""Module ``jobs``: queue an agent job, follow its progress, abandon it (S08).

The API authorizes a job command (``propose`` in the context), records it in
the jobs store (D14) and returns; no model is built in an HTTP request. The
worker (``python -m services.jobs``) runs it; the result is a pending proposal
that a person decides and applies through the review endpoints. The command's
``request_id`` is the ALM idempotency key: the same command again returns the
same job, another command under that id is a 409.

Progress is a server-sent-events stream: ``status`` events (``StatusEvent``)
and ``progress`` events (``alm.event/1`` of ``agent_system.events``), with the
event's sequence as ``id`` so that a client reconnects with ``Last-Event-ID``.
Neither carries a command, a prompt, a document or a learner's text. The
stream ends after the job's final status, or after ``job_stream_seconds``.

An administrator abandons a job: a queued job is never started; a running job
whose worker was interrupted has its ALM request abandoned, as the CLI
``abandon`` does.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Header, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from starlette.exceptions import HTTPException

from learning.contracts import EntityRef, Record, Text
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, WRITE_ERRORS, context_reader, context_writer, open_context
from services.api_common.errors import stream_error_responses
from services.api_common.registry import ApiModule
from services.jobs.kinds import JobCommand
from services.jobs.store import FINAL, JobRecord, JobStatus, JobStore, StatusEvent


class JobRequest(Record):
    """A job command with the client's ``request_id``, the ALM idempotency key."""
    request_id: Text
    job: JobCommand


class JobView(Record):
    """A job: its exact command, its status and, once ended, its pending proposal or the reason it ended."""
    context_id: Text
    request_id: Text
    subject_key: Text
    job: JobCommand
    status: JobStatus
    proposal_refs: tuple[EntityRef, ...]
    detail: Text | None = None
    created: Text
    updated: Text


def _view(job: JobRecord) -> JobView:
    return JobView(context_id=job.context_id, request_id=job.request_id, subject_key=job.subject_key,
                   job=job.command, status=job.status, proposal_refs=job.proposal_refs, detail=job.detail,
                   created=job.created, updated=job.updated)


def configure(app, settings) -> None:
    app.state.jobs_store = None if settings.jobs_store is None else settings.jobs_store.get_secret_value()
    app.state.job_poll_seconds = settings.job_poll_seconds
    app.state.job_stream_seconds = settings.job_stream_seconds
    app.state.job_wait = time.sleep


def _jobs(request: Request) -> JobStore:
    return JobStore(request.app.state.jobs_store)


def _job(jobs: JobStore, context_id: str, request_id: str) -> JobRecord:
    job = jobs.get(context_id, request_id)
    if job is None:
        raise HTTPException(404, 'Job not found')
    return job


def job_follower(context_id: str, request_id: str, request: Request,
                 principal: Principal = Depends(context_reader)) -> JobRecord:
    """The job, once the subject may follow jobs in its context: checked before any stream starts."""
    with open_context(request, context_id) as service:
        service.authorize_jobs(context_id, principal.subject_key)
    with _jobs(request) as jobs:
        return _job(jobs, context_id, request_id)


router = APIRouter(tags=['jobs'])


@router.post('/contexts/{context_id}/jobs', response_model=JobView, responses=WRITE_ERRORS,
             summary='Queue an agent job; the same request id and command return the same job, another command 409')
def queue(context_id: str, body: JobRequest, request: Request, principal: Principal = Depends(context_writer)):
    with open_context(request, context_id) as service:
        service.authorize_jobs(context_id, principal.subject_key)
    with _jobs(request) as jobs:
        job, _ = jobs.submit(context_id, body.request_id, principal.subject_key, body.job.kind,
                             body.job.model_dump(mode='json'))
    return _view(job)


@router.get('/contexts/{context_id}/jobs/{request_id}', response_model=JobView, responses=READ_ERRORS,
            summary='A job with its status and, once ended, its pending proposal or the reason it ended')
def read(job: JobRecord = Depends(job_follower)):
    return _view(job)


@router.get('/contexts/{context_id}/jobs/{request_id}/events', response_class=EventSourceResponse,
            responses=stream_error_responses(401, 403, 404, 409, 422, 500),
            summary='Server-sent events: status and content-free progress, until the job ends; resume with Last-Event-ID')
def follow(request: Request, job: JobRecord = Depends(job_follower),
           last_event_id: str | None = Header(None, alias='Last-Event-ID')):
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
    state = request.app.state
    deadline = time.monotonic() + state.job_stream_seconds
    while True:
        # A new connection each time: the generator may resume on another thread. The status is
        # read first, so a job that has ended has its final event in the batch read after it.
        with _jobs(request) as jobs:
            ended = jobs.get(job.context_id, job.request_id).status in FINAL
            batch = jobs.events(job.context_id, job.request_id, after)
        for event in batch:
            after = event.seq
            yield ServerSentEvent(raw_data=event.data, event=event.name, id=str(event.seq))
            if event.name == 'status' and StatusEvent.model_validate_json(event.data).status in FINAL:
                return
        if ended or time.monotonic() >= deadline:
            return
        state.job_wait(state.job_poll_seconds)


@router.post('/contexts/{context_id}/jobs/{request_id}/abandonment', response_model=JobView, responses=WRITE_ERRORS,
             summary='Abandon a queued or interrupted job (administrators); 409 once the job has ended')
def abandon(context_id: str, request_id: str, request: Request, principal: Principal = Depends(context_writer)):
    with _jobs(request) as jobs, open_context(request, context_id) as service:
        service.authorize_abandonment(context_id, principal.subject_key)
        job = _job(jobs, context_id, request_id)
        if job.status == 'QUEUED':
            done = jobs.transition(context_id, request_id, {'QUEUED'}, 'ABANDONED')
        elif job.status == 'RUNNING':
            # 409 while the worker has not reserved the request yet, or after it recorded the outcome.
            service.abandon_request(context_id, principal.subject_key, request_id)
            done = jobs.transition(context_id, request_id, {'RUNNING'}, 'ABANDONED')
        else:
            done = None
        if done is None:
            current = jobs.get(context_id, request_id)
            if job.status == 'RUNNING' and current.status == 'ABANDONED':
                return _view(current)
            raise HTTPException(409, 'The job has ended or changed; reload it')
    return _view(done)


MODULE = ApiModule('jobs', router)
