"""Module ``review``: the review inbox, decisions and application of approved proposals.

A decision carries the review payload key of the payload the reviewer saw. If
that key or the revision it belongs to is no longer current, the decision is
refused with 409 before anything is written; the client reloads and reviews
again. An application carries an operation id: a replay with the same id
returns the same change. Reviewer authority is checked by the core exactly as
for the CLI ``decide`` and ``apply``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request

from learning.contracts import Entity, EntityRef, Record, Text
from learning.review import PendingProposal
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, WRITE_ERRORS, context_reader, context_writer, open_context
from services.api_common.registry import ApiModule


class PendingProposals(Record):
    """Newest first. A decision must carry the ``review_payload_key`` of the payload the reviewer saw."""
    proposals: tuple[PendingProposal, ...]


class DecisionRequest(Record):
    """A decision on ``target``, the exact revision the reviewer saw, as the CLI ``decide``."""
    target: EntityRef
    decision: Literal['APPROVE', 'REJECT', 'REQUEST_REVISION']
    reason: Text
    review_payload_key: Text


class ApplicationRequest(Record):
    """Apply an approved proposal, as the CLI ``apply``; ``operation_id`` makes a retry a replay."""
    proposal: EntityRef
    operation_id: Text


router = APIRouter(tags=['review'])


@router.get('/contexts/{context_id}/pending-proposals', response_model=PendingProposals, responses=READ_ERRORS,
            summary='Proposals awaiting a decision; none for a learner-only subject, as in show')
def pending_proposals(context_id: str, request: Request, principal: Principal = Depends(context_reader)):
    with open_context(request, context_id) as service:
        return PendingProposals(proposals=service.pending_proposals(context_id, principal.subject_key))


@router.post('/contexts/{context_id}/decisions', response_model=Entity, responses=WRITE_ERRORS,
             summary='Record a human decision on the reviewed payload; 409 if its key or revision is stale')
def decide(context_id: str, body: DecisionRequest, request: Request, principal: Principal = Depends(context_writer)):
    with open_context(request, context_id) as service:
        return service.decide(context_id, principal.subject_key, body.target, body.decision, body.reason,
                              expected_key=body.review_payload_key)


@router.post('/contexts/{context_id}/applications', response_model=Entity, responses=WRITE_ERRORS,
             summary='Apply an approved proposal; a replay of the operation id returns the same change')
def apply(context_id: str, body: ApplicationRequest, request: Request, principal: Principal = Depends(context_writer)):
    with open_context(request, context_id) as service:
        return service.apply(context_id, principal.subject_key, body.proposal, body.operation_id)


MODULE = ApiModule('review', router)
