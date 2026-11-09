"""Module ``review``: proposals awaiting a decision, with the exact payload and its review key.

Decisions and application are S06; this module only reads.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from learning.contracts import Record
from learning.review import PendingProposal
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, context_reader, open_context
from services.api_common.registry import ApiModule


class PendingProposals(Record):
    """Newest first. A decision must carry the ``review_payload_key`` of the payload the reviewer saw."""
    proposals: tuple[PendingProposal, ...]


router = APIRouter(tags=['review'])


@router.get('/contexts/{context_id}/pending-proposals', response_model=PendingProposals, responses=READ_ERRORS,
            summary='Proposals awaiting a decision; none for a learner-only subject, as in show')
def pending_proposals(context_id: str, request: Request, principal: Principal = Depends(context_reader)):
    with open_context(request, context_id) as service:
        return PendingProposals(proposals=service.pending_proposals(context_id, principal.subject_key))


MODULE = ApiModule('review', router)
