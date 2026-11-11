"""Progressive refinement of a syllabus proposal (S09b, D18): a Curator revision or a teacher's edit.

Both record a new pending proposal built on the same input as the proposal they
refine: the AIM-PRO source snapshot and the excerpts it holds, prepared and
accepted or retrieved. Nothing is searched or prepared again, so the course must
still be at that proposal's step: its base version, or the version its
application produced (owner decision 4). Otherwise the teacher prepares the
sources and generates again.

- A **revision** answers a revision request (``REQUEST_REVISION``) on the
  proposal: the Curator receives the previous syllabus and the reasons of the
  whole chain, first to last, and its result is reviewed by the agent as any
  generated syllabus.
- An **edit** is the teacher's own syllabus. It passes the same checks as a
  generated one and is recorded as a proposal by that teacher, declared not
  reviewed by the agent; the teacher may approve and apply it.

The new proposal names the one it refines, which the teacher view compares it with.
"""

import logging

from aimpro.lead import ReviewError
from aimpro.syllabus import SyllabusDraft, SyllabusRevision, checked_syllabus, generate
from aimpro.syllabus_state import SyllabusResult, candidates, proposed, proposed_result
from learning.context import LearningRequest
from learning.contracts import EntityRef
from learning.decisions import create_proposal, save_proposal
from learning.projects import _authorize, _draft
from learning.store import StateConflict, canonical


NO_REQUEST = 'A revision needs a revision request on the latest revision of this syllabus proposal'
STALE = 'The course changed after this syllabus proposal; prepare the sources and generate the syllabus again'


def _at_step(store, context, proposal):
    """Whether the course is still at the step of ``proposal``: its base version or the version it applied."""
    root = context.snapshot.context
    if proposal.fields['baseContextVersion'] == root.version:
        return True
    return any(EntityRef.model_validate(change.fields['cause']).id == proposal.id and
               change.fields['newVersion'] == root.version for change in store.owned(root.id, 'StateChange'))


def _base(service, context, proposal_id):
    _authorize(context)
    _draft(context)
    base = proposed(service.store, context, proposal_id)
    if not _at_step(service.store, context, base.proposal):
        raise ReviewError(STALE)
    return base


def _explanation(summary, base, draft, **refinement):
    data = base.source
    return summary + ' ' + canonical({
        'refines': base.proposal.ref.model_dump(mode='json'), **refinement,
        'source_sha256': data.source.source_sha256, 'metamodel_fingerprint': data.metamodel_fingerprint,
        'source_diagnostics': data.source.diagnostics, 'contract_findings': data.findings,
        'syllabus_gaps': draft.gaps})


def _record(service, context_id, request_id, context, base, draft, verdict, explanation, attempts=(), **refinement):
    """Save the new proposal and the request's result; the caller holds the write transaction."""
    root = context.snapshot.context
    saved = candidates(base.source, draft, verdict, context, retrieval_trace=base.trace,
                       revises=base.proposal.ref, **refinement)
    proposal = create_proposal(context, (root.ref,), saved, explanation)
    result = proposed_result('The refined syllabus awaits human review.', proposal, attempts, verdict)
    save_proposal(service.store, context, proposal, saved)
    service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
    return result


def revise_syllabus(service, context_id, subject_key, *, request_id, proposal, authoring_factory):
    """A Curator revision of ``proposal`` (an id) after a revision request; replayed by ``request_id``."""
    context = service._context(context_id, subject_key)
    root = context.snapshot.context
    LearningRequest(request_id=request_id, context_ref=root.ref, subject_key=subject_key,
                    text='Revise a Curator syllabus proposal', intent='CURATE')
    payload = canonical({'operation': 'AIMPRO_SYLLABUS_REVISE', 'subject_key': subject_key, 'proposal': proposal})
    cached = service.store.request_result(request_id, context_id, payload)
    if cached is not None:
        return SyllabusResult.model_validate(cached)
    base = _base(service, context, proposal)
    decision = base.proposal.fields.get('decision')
    decision = decision and service.store.read(EntityRef.model_validate(decision), owner=context_id)
    if base.proposal.fields['status'] != 'DRAFT' or not decision or decision.fields['decision'] != 'REQUEST_REVISION':
        raise ReviewError(NO_REQUEST)
    reasons = (*base.artifact.revision_reasons, decision.fields['reason'])
    cached = service.store.claim_request(request_id, context_id, payload)
    if cached is not None:
        return SyllabusResult.model_validate(cached)
    attempts = ()
    try:
        dispatcher, lead, budget = authoring_factory()
        draft, verdict, attempts = generate(base.source, dispatcher=dispatcher, lead=lead, max_context_chars=budget,
                                  revision=SyllabusRevision(previous=base.artifact.draft, reasons=reasons))
        explanation = _explanation('Review a Curator revision of a syllabus proposal, asked by the teacher; '
                                   'no approval or learner progress is inferred.', base, draft,
                                   revision_reasons=list(reasons))
        with service.store.write_transaction():
            if service.store.read_context(context_id).version != root.version:
                raise StateConflict('Context changed during syllabus revision')
            return _record(service, context_id, request_id, context, base, draft, verdict, explanation,
                           attempts=attempts, revision_reasons=reasons)
    except Exception as error:
        # ReviewError messages are fixed application text, never model or course content: the author may read them.
        reason = f' ({error})' if isinstance(error, ReviewError) else ''
        logging.getLogger('agent_system').warning('Syllabus revision failed (%s)%s', type(error).__name__, reason)
        result = SyllabusResult(kind='FAILURE', content=f'Syllabus revision did not complete{reason}; no proposal was applied.',
                                attempts=getattr(error, 'attempts', attempts))
    try:
        service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
    except StateConflict:
        return SyllabusResult.model_validate(service.store.claim_request(request_id, context_id, payload))
    return result


def edit_syllabus(service, context_id, subject_key, *, request_id, proposal, draft):
    """The teacher's own syllabus in place of ``proposal`` (an id); no model. Replayed by ``request_id``.

    The checks, the proposal and the request's result share one write transaction.
    """
    draft = SyllabusDraft.model_validate(draft.model_dump(mode='json') if hasattr(draft, 'model_dump') else draft)
    payload = canonical({'operation': 'AIMPRO_SYLLABUS_EDIT', 'subject_key': subject_key, 'proposal': proposal,
                         'draft': draft.model_dump(mode='json')})
    with service.store.write_transaction():
        context = service._context(context_id, subject_key)
        LearningRequest(request_id=request_id, context_ref=context.snapshot.context.ref, subject_key=subject_key,
                        text='Edit a syllabus proposal', intent='CURATE')
        cached = service.store.request_result(request_id, context_id, payload)
        if cached is not None:
            return SyllabusResult.model_validate(cached)
        base = _base(service, context, proposal)
        draft = checked_syllabus(base.source, draft)
        service.store.reserve_request(request_id, context_id, payload)
        explanation = _explanation("Review a teacher's edit of a syllabus proposal, not reviewed by the agent; "
                                   'no approval or learner progress is inferred.', base, draft, edited_by=subject_key)
        return _record(service, context_id, request_id, context, base, draft, None, explanation,
                       revision_reasons=base.artifact.revision_reasons, edited_by=subject_key)
