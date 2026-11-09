"""Module ``releases``: release inspection, as the CLI ``show-release`` prints it."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from learning.contracts import EntityRef
from learning.releases import ReleaseInspection
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, context_reader, open_context
from services.api_common.registry import ApiModule


router = APIRouter(tags=['releases'])


@router.get('/contexts/{context_id}/resources/{resource_id}/versions/{version}/release',
            response_model=ReleaseInspection, responses=READ_ERRORS,
            summary='Receipts, the exact frozen closure and findings of this release (CLI show-release)')
def release_inspection(context_id: str, resource_id: str, version: str, request: Request,
                       principal: Principal = Depends(context_reader)):
    release = EntityRef(type='Resource', id=resource_id, version=version)
    with open_context(request, context_id) as service:
        return service.inspect_release(context_id, principal.subject_key, release)


MODULE = ApiModule('releases', router)
