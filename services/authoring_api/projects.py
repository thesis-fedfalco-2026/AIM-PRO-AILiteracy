"""Module ``projects``: project initialization, project inspection and approved syllabi, as the CLI does them.

A project is initialized from the approved Curator syllabus of the course's
current outline (S09a); the result is a pending proposal that a person decides
and applies through the review endpoints. Completion rules (S09c2) are proposed
the same way: the fixed rule on every process node of the project's design.

The Evaluator, Teacher and Trainer jobs (S09c) keep the review agent's verdict
of each of their drafts with the request's result; the subject who ran the
job reads them here. The review agent's reason is model text.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from starlette.exceptions import HTTPException

from aimpro.generators import GenerationAttempt
from aimpro.syllabus_state import ApprovedSyllabus
from learning.contracts import EntityRef, Record, Text
from learning.projects import CompletionRules, ProjectInitialization, ProjectInspection, ProjectProposal
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, WRITE_ERRORS, context_reader, context_writer, open_context
from services.api_common.registry import ApiModule


class ProjectInitializationRequest(ProjectInitialization):
    """``init-authoring-project``: the exact approved syllabus and base context, with the ALM request id."""
    request_id: Text


class CompletionRulesRequest(CompletionRules):
    """``propose-completion-rules``: the exact selected project and base context, with the ALM request id."""
    request_id: Text


class GenerationReviews(Record):
    """The drafts of an ended Evaluator, Teacher or Trainer job, first to last; ``review.reason`` is the review agent's text."""
    request_id: Text
    outcome: Literal['PROPOSAL', 'FAILURE']
    attempts: tuple[GenerationAttempt, ...]


router = APIRouter(tags=['projects'])


@router.post('/contexts/{context_id}/projects', response_model=ProjectProposal, responses=WRITE_ERRORS,
             summary='Propose a project from an approved syllabus (CLI init-authoring-project); a request id replays')
def initialize_project(context_id: str, body: ProjectInitializationRequest, request: Request,
                       principal: Principal = Depends(context_writer)):
    with open_context(request, context_id) as service:
        return service.initialize_authoring_project(context_id, principal.subject_key,
            body.model_dump(exclude={'request_id'}), request_id=body.request_id)


@router.post('/contexts/{context_id}/completion-rules', response_model=ProjectProposal, responses=WRITE_ERRORS,
             summary='Propose the fixed completion rule on every node of the project design (CLI propose-completion-rules)')
def propose_completion_rules(context_id: str, body: CompletionRulesRequest, request: Request,
                             principal: Principal = Depends(context_writer)):
    with open_context(request, context_id) as service:
        return service.propose_completion_rules(context_id, principal.subject_key,
            body.model_dump(exclude={'request_id'}), request_id=body.request_id)


@router.get('/contexts/{context_id}/designs/{design_id}/versions/{version}/syllabus',
            response_model=ApprovedSyllabus, responses=READ_ERRORS,
            summary='The approved syllabus of the current Curator outline (CLI show-aimpro-syllabus)')
def design_syllabus(context_id: str, design_id: str, version: str, request: Request,
                    principal: Principal = Depends(context_reader)):
    design = EntityRef(type='LearningDesign', id=design_id, version=version)
    with open_context(request, context_id) as service:
        return service.approved_aimpro_syllabus(context_id, principal.subject_key, design)


@router.get('/contexts/{context_id}/projects/{project_id}', response_model=ProjectInspection,
            responses=READ_ERRORS,
            summary='Current selections, approval receipts and stale dependencies (CLI show-authoring-project)')
def project_inspection(context_id: str, project_id: str, request: Request,
                       principal: Principal = Depends(context_reader)):
    with open_context(request, context_id) as service:
        return service.inspect_authoring_project(context_id, principal.subject_key, project_id)


@router.get('/contexts/{context_id}/resources/{resource_id}/versions/{version}/project-syllabus',
            response_model=ApprovedSyllabus, responses=READ_ERRORS,
            summary='The approved syllabus of this exact current project revision (CLI show-project-syllabus)')
def project_syllabus(context_id: str, resource_id: str, version: str, request: Request,
                     principal: Principal = Depends(context_reader)):
    project = EntityRef(type='Resource', id=resource_id, version=version)
    with open_context(request, context_id) as service:
        return service.approved_project_syllabus(context_id, principal.subject_key, project)



@router.get('/contexts/{context_id}/generation-reviews/{request_id}', response_model=GenerationReviews,
            responses=READ_ERRORS, summary="How the review agent judged each draft of the subject's Evaluator, Teacher or Trainer job")
def generation_reviews(context_id: str, request_id: str, request: Request, principal: Principal = Depends(context_reader)):
    with open_context(request, context_id) as service:
        service.authorize_jobs(context_id, principal.subject_key)
        result = service.project_generation_request(context_id, principal.subject_key, request_id)
    if result is None or result.kind not in ('PROPOSAL', 'FAILURE'):
        raise HTTPException(404, 'No ended generator job of this subject under this id')
    return GenerationReviews(request_id=request_id, outcome=result.kind, attempts=result.attempts)


MODULE = ApiModule('projects', router)
