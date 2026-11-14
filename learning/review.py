"""Read-only review inbox: proposals awaiting a decision, with the exact payload a reviewer sees."""

from __future__ import annotations

from learning.contracts import Entity, Record, Text
from learning.decisions import proposal_candidates, review_payload_key


class PendingProposal(Record):
    proposal: Entity
    candidates: tuple[Entity, ...]
    review_payload_key: Text


def pending_proposals(store, context) -> tuple[PendingProposal, ...]:
    """The latest revision of every proposal of the context that awaits a decision, newest first.

    ``review_payload_key`` covers the proposal and its candidates exactly as
    :func:`learning.decisions.record_decision` checks them; a decision on any
    other payload is refused.
    """
    found = []
    for proposal in store.owned(context.snapshot.context.id, 'ChangeProposal'):
        if proposal.fields['status'] != 'AWAITING_DECISION':
            continue
        candidates = proposal_candidates(store, proposal)
        found.append(PendingProposal(proposal=proposal, candidates=candidates,
                                     review_payload_key=review_payload_key(proposal, candidates)))
    return tuple(found)


def proposal_review(store, context, proposal_id) -> PendingProposal | None:
    """The latest revision of one proposal of the context with its candidates, whatever its status (S09c2).

    ``review_payload_key`` is the key a decision would carry; only a proposal awaiting a decision accepts one.
    ``None`` when the context has no proposal under ``proposal_id``.
    """
    proposal = next((p for p in store.owned(context.snapshot.context.id, 'ChangeProposal') if p.id == proposal_id), None)
    if proposal is None:
        return None
    candidates = proposal_candidates(store, proposal)
    return PendingProposal(proposal=proposal, candidates=candidates,
                           review_payload_key=review_payload_key(proposal, candidates))
