"""Module ``projects``: project initialization, project inspection and approved syllabi, as the CLI does them.

A project is initialized from the approved Curator syllabus of the course's
current outline (S09a); the result is a pending proposal that a person decides
and applies through the review endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from aimpro.syllabus_state import ApprovedSyllabus
from learning.contracts import EntityRef, Text
from learning.projects import ProjectInitialization, ProjectInspection, ProjectProposal
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, WRITE_ERRORS, context_reader, context_writer, open_context
from services.api_common.registry import ApiModule


class ProjectInitializationRequest(ProjectInitialization):
    """``init-authoring-project``: the exact approved syllabus and base context, with the ALM request id."""
    request_id: Text


router = APIRouter(tags=['projects'])


@router.post('/contexts/{context_id}/projects', response_model=ProjectProposal, responses=WRITE_ERRORS,
             summary='Propose a project from an approved syllabus (CLI init-authoring-project); a request id replays')
def initialize_project(context_id: str, body: ProjectInitializationRequest, request: Request,
                       principal: Principal = Depends(context_writer)):
    with open_context(request, context_id) as service:
        return service.initialize_authoring_project(context_id, principal.subject_key,
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


MODULE = ApiModule('projects', router)
