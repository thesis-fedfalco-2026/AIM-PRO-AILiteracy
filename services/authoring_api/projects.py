"""Module ``projects``: project inspection and the approved project syllabus, as the CLI prints them."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from aimpro.syllabus_state import ApprovedSyllabus
from learning.contracts import EntityRef
from learning.projects import ProjectInspection
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, context_reader, open_context
from services.api_common.registry import ApiModule


router = APIRouter(tags=['projects'])


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
