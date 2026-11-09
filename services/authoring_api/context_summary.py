"""Module ``contexts``: the context summary, the records the CLI ``show`` prints for the subject."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from learning.contracts import Entity, Finding, Record
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, context_reader, open_context
from services.api_common.registry import ApiModule



class ContextSummary(Record):
    """The context, the entities the subject may see and the snapshot findings.

    A learner-only subject sees only the context, its own participant record and
    its own learning records, never proposals, decisions or other participants.
    """
    context: Entity
    entities: tuple[Entity, ...]
    findings: tuple[Finding, ...]


router = APIRouter(tags=['contexts'])


@router.get('/contexts/{context_id}', response_model=ContextSummary, responses=READ_ERRORS,
            summary='Context summary with the same redaction as the CLI show')
def context_summary(context_id: str, request: Request, principal: Principal = Depends(context_reader)):
    with open_context(request, context_id) as service:
        return ContextSummary.model_validate(service.show(context_id, principal.subject_key))


MODULE = ApiModule('contexts', router)
