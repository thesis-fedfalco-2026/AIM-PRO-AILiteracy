"""Module ``syllabus``: a syllabus proposal in words, compared, and edited by the teacher (S09b, D18).

A syllabus proposal is read with the texts a teacher reviews: the statement of
each learning target, its competencies and practices, and the cited excerpts
with the purpose and limitations written when the sources were prepared. It is
compared with the proposal it refines (a Curator revision or a teacher's edit)
and with the course's applied syllabus, units paired by learning target
(:mod:`aimpro.syllabus_compare`).

A teacher's edit is recorded here, without a model: a new proposal by that
teacher that passes the same checks as a generated syllabus and is declared not
reviewed by the agent. A Curator revision is the job ``revise-aimpro-syllabus``.

Every draft the Curator made for a syllabus job is read back with how it was
judged (Chat 20): the review agent's verdict, whose ``reason`` is the agent's
own text, or the fixed text of the check that refused it.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from starlette.exceptions import HTTPException

from aimpro.didactic import targets
from aimpro.syllabus import SyllabusAttempt, SyllabusDraft, SyllabusVerdict
from aimpro.syllabus_compare import SyllabusComparison, compare
from aimpro.syllabus_state import NoSyllabus
from learning.contracts import EntityRef, Record, Text
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, WRITE_ERRORS, context_reader, context_writer, open_context
from services.api_common.registry import ApiModule


class Competency(Record):
    id: Text
    name: str
    description: str


class Practice(Record):
    id: Text
    # The practice's class in the model, as the strategy is named in the course.
    name: Text
    # How the practice works in the scenario (``inPractice``), else its rationale.
    text: str


class Target(Record):
    id: Text
    statement: str
    competencies: tuple[Competency, ...]
    # The practices a unit on this target may name.
    practices: tuple[Practice, ...]


class CitedExcerpt(Record):
    """An excerpt a unit may cite; ``purpose`` and ``limitations`` exist for prepared sources only."""
    resource_id: Text
    resource_version: Text
    document_id: Text
    title: Text
    uri: Text
    licence: Text
    text: str
    purpose: Text | None
    limitations: tuple[Text, ...]


class SyllabusRecord(Record):
    proposal: EntityRef
    status: Text
    responsible: Text
    draft: SyllabusDraft
    reviewed_by_agent: bool
    review: SyllabusVerdict | None
    edited_by: Text | None
    # The reasons of the revision requests that led to this syllabus, first to last.
    revision_reasons: tuple[Text, ...]


class SyllabusProposalView(Record):
    """The syllabus of a proposal, the one it refines and the course's applied syllabus, with their texts."""
    syllabus: SyllabusRecord
    targets: tuple[Target, ...]
    excerpts: tuple[CitedExcerpt, ...]
    refined: SyllabusRecord | None
    compared_with_refined: SyllabusComparison | None
    course_design: Literal['NONE', 'SYLLABUS', 'OTHER'] = 'NONE'
    current: SyllabusRecord | None
    compared_with_current: SyllabusComparison


class SyllabusEdit(Record):
    """The teacher's whole syllabus in place of ``proposal`` (an id); ``request_id`` makes a retry a replay."""
    request_id: Text
    proposal: Text
    draft: SyllabusDraft


class EditedSyllabus(Record):
    proposal: EntityRef


class SyllabusReviews(Record):
    """The Curator's drafts of an ended syllabus job, first to last; ``review.reason`` is the review agent's text."""
    request_id: Text
    outcome: Literal['PROPOSAL', 'FAILURE']
    attempts: tuple[SyllabusAttempt, ...]


def _record(found) -> SyllabusRecord:
    artifact = found.artifact
    return SyllabusRecord(proposal=found.proposal.ref, status=found.proposal.fields['status'],
                          responsible=found.proposal.provenance.responsible, draft=artifact.draft,
                          reviewed_by_agent=artifact.review is not None, review=artifact.review,
                          edited_by=artifact.edited_by, revision_reasons=artifact.revision_reasons)


def _targets(data) -> list[Target]:
    index = {o.id: o for o in data.source.objects}
    found = []
    for target_id, practices in targets(data).items():
        target = index[target_id]
        found.append(Target(
            id=target_id, statement=str(target.attributes.get('description') or ''),
            competencies=tuple(Competency(id=c, name=str(index[c].attributes.get('title') or c),
                                          description=str(index[c].attributes.get('description') or ''))
                               for c in target.references['competency'] if c in index),
            practices=tuple(Practice(id=p, name=index[p].class_name,
                                     text=str(index[p].attributes.get('inPractice') or
                                              index[p].attributes.get('rationale') or ''))
                            for p in sorted(practices) if p in index)))
    return found


def _excerpts(data) -> list[CitedExcerpt]:
    evidence = data.corpus_evidence
    if evidence is None:
        return []
    selected = {(d.resource_id, d.resource_version, d.document_id): d
                for d in (evidence.selection.documents if evidence.selection else ())}
    found = []
    for resource in evidence.resources:
        for document in resource.documents:
            chosen = selected.get((resource.identity, resource.version, document.id))
            found.append(CitedExcerpt(resource_id=resource.identity, resource_version=resource.version,
                                      document_id=document.id, title=resource.title, uri=resource.uri,
                                      licence=resource.licence, text=document.text,
                                      purpose=chosen.purpose if chosen else None,
                                      limitations=chosen.limitations if chosen else ()))
    return found


def _unique(items, key):
    seen = {}
    for item in items:
        seen.setdefault(key(item), item)
    return tuple(seen.values())


def proposal_view(found, refined, current, design) -> SyllabusProposalView:
    sources = [s.source for s in (found, refined, current) if s is not None]
    return SyllabusProposalView(
        syllabus=_record(found),
        targets=_unique((t for data in sources for t in _targets(data)), lambda t: t.id),
        excerpts=_unique((e for data in sources for e in _excerpts(data)),
                         lambda e: (e.resource_id, e.resource_version, e.document_id)),
        refined=refined and _record(refined),
        compared_with_refined=refined and compare(refined.artifact.draft, found.artifact.draft),
        course_design=design, current=current and _record(current),
        compared_with_current=compare(current.artifact.draft if current else None, found.artifact.draft))


router = APIRouter(tags=['syllabus'])


@router.get('/contexts/{context_id}/syllabus-proposals/{proposal_id}', response_model=SyllabusProposalView,
            responses=READ_ERRORS,
            summary='A syllabus proposal in words, compared with the proposal it refines and the applied syllabus')
def syllabus_proposal(context_id: str, proposal_id: str, request: Request,
                      principal: Principal = Depends(context_reader)):
    with open_context(request, context_id) as service:
        try:
            found = service.aimpro_syllabus_proposal(context_id, principal.subject_key, proposal_id)
        except NoSyllabus:
            raise HTTPException(404, 'No syllabus proposal under this id') from None
    return proposal_view(*found)


@router.post('/contexts/{context_id}/syllabus-edits', response_model=EditedSyllabus, responses=WRITE_ERRORS,
             summary="Record a teacher's edit of a syllabus proposal as a new proposal by that teacher")
def syllabus_edit(context_id: str, body: SyllabusEdit, request: Request, principal: Principal = Depends(context_writer)):
    with open_context(request, context_id) as service:
        try:
            response = service.edit_aimpro_syllabus(context_id, principal.subject_key, body.proposal, body.draft,
                                                    request_id=body.request_id)
        except NoSyllabus:
            raise HTTPException(404, 'No syllabus proposal under this id') from None
    return EditedSyllabus(proposal=response.proposal_refs[0])


@router.get('/contexts/{context_id}/syllabus-reviews/{request_id}', response_model=SyllabusReviews,
            responses=READ_ERRORS, summary="How the review agent judged each draft of the subject's syllabus job")
def syllabus_reviews(context_id: str, request_id: str, request: Request, principal: Principal = Depends(context_reader)):
    with open_context(request, context_id) as service:
        service.authorize_jobs(context_id, principal.subject_key)
        result = service.aimpro_syllabus_request(context_id, principal.subject_key, request_id)
    if result is None or result.kind not in ('PROPOSAL', 'FAILURE'):
        raise HTTPException(404, 'No ended syllabus job of this subject under this id')
    return SyllabusReviews(request_id=request_id, outcome=result.kind, attempts=result.attempts)


MODULE = ApiModule('syllabus', router)
