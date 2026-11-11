"""Persist and resolve exact reviewed syllabuses using existing ALM entities."""

from dataclasses import replace
import json
import logging
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from aimpro.contracts import encoded
from aimpro.lead import LeadInput, ReviewError
from aimpro.lead_types import Record, Text
from aimpro.source_selection import RetrievalTrace
from aimpro.syllabus import (CURATOR, NOT_PASSED, SyllabusAttempt, SyllabusDraft, SyllabusVerdict, accepted,
                             checked_syllabus)
from learning.contracts import Entity, EntityRef, Provenance, entity_data, make_entity
from learning.decisions import approval_valid, proposal_candidates, review_payload_key
from learning.metamodel import validate_entity
from learning.outputs import LearningResponse
from learning.store import canonical


class SyllabusResult(LearningResponse):
    """The recorded result of a Curator syllabus request, with every attempt the Curator made (Chat 20).

    ``attempts`` is omitted when empty, so results recorded before it, and of requests without a Curator draft,
    keep their exact shape. ``content`` stays fixed application text; the reviewer's own words are in ``attempts``.
    """
    attempts: tuple[SyllabusAttempt, ...] = Field((), exclude_if=lambda value: not value)
    # Fixed application text for the author when the proposal was not accepted by the review agent (issue #112).
    notice: Text | None = Field(None, exclude_if=lambda value: value is None)


NOT_ACCEPTED = (f'The review agent accepted no draft ({NOT_PASSED}); the last draft that passed the checks is '
                'proposed with its assessment, for the teacher to decide.')


def proposed_result(content, proposal, attempts, verdict) -> SyllabusResult:
    """The result of a syllabus proposal, with :data:`NOT_ACCEPTED` when the review agent did not accept it.

    ``verdict`` is ``None`` for a teacher's edit, which the review agent does not review.
    """
    notice = None if verdict is None or accepted(verdict) else NOT_ACCEPTED
    if notice is not None:
        logging.getLogger('agent_system').warning('Syllabus proposed without the review agent\'s acceptance')
    return SyllabusResult(kind='PROPOSAL', content=content, proposal_refs=(proposal.ref,),
                          application_status='pending', attempts=attempts, notice=notice)


class UnitLink(Record):
    key: Text
    node: EntityRef


class SyllabusArtifact(Record):
    format: Literal['aimpro-syllabus'] = 'aimpro-syllabus'
    format_version: Literal[1] = 1
    context_id: Text
    curator: Literal['syllabus-designer'] = CURATOR
    outline: EntityRef
    source_snapshot: EntityRef
    units: tuple[UnitLink, ...] = Field(min_length=1)
    draft: SyllabusDraft
    # A teacher's edit (S09b) has no review by the agent; the teacher decides it as is.
    review: SyllabusVerdict | None = Field(None, exclude_if=lambda value: value is None)
    # The refinement chain (S09b), omitted when absent to keep the payloads of earlier syllabi unchanged.
    revises: EntityRef | None = Field(None, exclude_if=lambda value: value is None)
    revision_reasons: tuple[Text, ...] = Field((), exclude_if=lambda value: not value)
    edited_by: Text | None = Field(None, exclude_if=lambda value: value is None)

    @model_validator(mode='after')
    def reviewed_unless_edited(self):
        if (self.review is None) != (self.edited_by is not None):
            raise ValueError('A syllabus is reviewed by the agent unless a teacher edited it')
        if self.edited_by is not None and self.revises is None:
            raise ValueError('An edited syllabus names the proposal it edits')
        if self.revises is not None and self.revises.type != 'ChangeProposal':
            raise ValueError('A syllabus revises a change proposal')
        return self


class ApprovedSyllabus(Record):
    syllabus: EntityRef
    artifact: SyllabusArtifact
    source: LeadInput
    proposal: EntityRef
    decision: EntityRef
    change: EntityRef


class NoSyllabus(ValueError):
    """The context has no proposal under this id, or the proposal holds no syllabus."""


class ProposedSyllabus(Record):
    """A syllabus proposal at its latest revision, whatever its status, with the input it was built on."""
    proposal: Entity
    syllabus: Entity
    artifact: SyllabusArtifact
    source: LeadInput
    trace: RetrievalTrace | None = None


def syllabus_artifact(entity):
    """The syllabus payload of a Resource, or ``None`` when it holds none."""
    if entity.type != 'Resource':
        return None
    try:
        raw = json.loads(entity.fields.get('contentOrLocator', ''))
    except (TypeError, ValueError):
        return None
    if not isinstance(raw, dict) or raw.get('format') != 'aimpro-syllabus':
        return None
    return SyllabusArtifact.model_validate(raw)


def proposed(store, context, proposal_id):
    """The syllabus of the context's proposal ``proposal_id``; ``ValueError`` when it proposes no syllabus."""
    root = context.snapshot.context
    proposal = next((p for p in store.owned(root.id, 'ChangeProposal') if p.id == proposal_id), None)
    if proposal is None:
        raise NoSyllabus('Unknown syllabus proposal')
    saved = proposal_candidates(store, proposal)
    found = [(c, artifact) for c in saved if (artifact := syllabus_artifact(c)) is not None]
    if len(found) != 1:
        raise NoSyllabus('The proposal holds no syllabus')
    syllabus, artifact = found[0]
    by_ref = {c.ref: c for c in saved}
    source = by_ref.get(artifact.source_snapshot)
    if artifact.context_id != root.id or source is None:
        raise ValueError('Syllabus payload belongs to another outline or context')
    trace = None
    for raw in source.fields.get('derivedFrom', []):
        linked = by_ref.get(EntityRef.model_validate(raw))
        if linked is not None and linked.id.endswith(':retrieval-trace'):
            trace = RetrievalTrace.model_validate_json(linked.fields['contentOrLocator'])
    return ProposedSyllabus(proposal=proposal, syllabus=syllabus, artifact=artifact,
                            source=LeadInput.model_validate_json(source.fields['contentOrLocator']), trace=trace)


def candidates(data, draft, verdict, context, *, retrieval_trace=None, revises=None, revision_reasons=(),
               edited_by=None):
    """The ALM records of a syllabus proposal; ``verdict`` is ``None`` only for a teacher's edit (``edited_by``)."""
    draft = checked_syllabus(data, draft)
    # The verdict is kept as given: a syllabus the review agent did not accept may be proposed (issue #112).
    verdict = None if verdict is None and edited_by is not None else SyllabusVerdict.model_validate(
        verdict.model_dump(mode='json'))
    root = context.snapshot.context
    if (root.fields['mode'], root.fields['status']) != ('PREPARATION', 'DRAFT'):
        raise ReviewError('Syllabus import requires a PREPARATION DRAFT context')
    prefix = 'aimpro-syllabus-' + uuid4().hex
    index = {o.id: o for o in data.source.objects}
    result = []

    def make(kind, key, fields, source_ids):
        value = make_entity(kind, prefix + ':' + key, fields, origin='GENERATED_PROPOSAL',
                            responsible=context.request.subject_key)
        value = value.model_copy(update={'provenance': Provenance(
            origin='GENERATED_PROPOSAL', responsible=context.request.subject_key,
            sources=[encoded({'source_sha256': data.source.source_sha256,
                'metamodel_fingerprint': data.metamodel_fingerprint, 'source_ids': list(source_ids)})],
            rationale='Local Curator syllabus proposal; not an AIM-PRO change or resource-use approval.')})
        value = validate_entity(entity_data(value), context.contract)
        result.append(value)
        return value

    def ref(value):
        return value.ref.model_dump()

    topics = {}
    for oid in data.source.competency_ids:
        obj = index[oid]
        topics[oid] = make('Topic', 'topic:' + oid, {
            'name': obj.attributes['title'], 'definition': obj.attributes['description']}, [oid])
    outcomes = {}
    for oid in dict.fromkeys(unit.source_target_id for unit in draft.units):
        obj = index[oid]
        outcomes[oid] = make('LearningOutcome', 'outcome:' + oid, {
            'statement': obj.attributes['description'],
            'topics': [ref(topics[c]) for c in obj.references['competency']]}, [oid])
    trace = None
    if retrieval_trace is not None:
        if (data.corpus_evidence is None or data.corpus_evidence.selection is None or
                data.corpus_evidence.selection.trace_sha256 != retrieval_trace.digest):
            raise ValueError('Source input does not match its recorded retrieval trace')
        trace = make('Resource', 'retrieval-trace', {
            'title': 'Source discovery and exact selection trace',
            'topics': [ref(t) for t in topics.values()],
            'contentOrLocator': retrieval_trace.model_dump_json(),
            'usageConditions': 'Retrieval audit only; neither pedagogical approval nor learner access.'}, [data.source.root_id])
    source = make('Resource', 'source-snapshot', {
        'title': 'AIM-PRO syllabus source snapshot and integration diagnostics',
        'contentOrLocator': encoded(data.model_dump(mode='json')),
        'topics': [ref(t) for t in topics.values()], 'derivedFrom': [ref(trace)] if trace else [],
        'usageConditions': 'Authoring provenance only; not an approved teaching resource.'}, [data.source.root_id])
    # Match the existing canonical corpus projection: queries do not redefine versions.
    scope = data.corpus_evidence.source_scope
    corpus_topic = validate_entity(entity_data(make_entity('Topic', 'corpus-topic:' + scope, {
        'name': scope + ' source corpus',
        'definition': 'Versioned source catalogue accessed through an authorized MCP search scope.'},
        responsible='corpus-retrieval')), context.contract)
    result.append(corpus_topic)
    cited = {c.resource_key for unit in draft.units for c in unit.corpus_citations}
    if data.corpus_evidence.selection is not None:
        # All explicitly selected excerpts belong to the reviewed source input,
        # including assessment context not cited by a particular outline unit.
        cited.update(r.key for r in data.corpus_evidence.resources)
    corpus = []
    for resource in data.corpus_evidence.resources:
        if resource.key not in cited:
            continue
        entity = make_entity('Resource', resource.identity, {
            'title': resource.title, 'contentOrLocator': resource.uri, 'topics': [ref(corpus_topic)],
            'usageConditions': 'Corpus licence assertion: ' + resource.licence +
                '. Usage and provenance require human review; no local resource approval is implied.'},
            version=resource.version, origin='GENERATED_PROPOSAL', responsible='corpus-retrieval')
        entity = entity.model_copy(update={'provenance': entity.provenance.model_copy(update={
            'sources': [resource.key, resource.source_scope]})})
        entity = validate_entity(entity_data(entity), context.contract)
        result.append(entity)
        corpus.append(entity)
    constraints = []
    for obj in data.source.objects:
        if (obj.package, obj.class_name) == ('iSQD', 'LearningTask'):
            raw = obj.attributes.get('constraints', [])
            constraints.extend(raw if isinstance(raw, list) else [raw])
    strategies = {}
    for oid in dict.fromkeys(p for unit in draft.units for p in unit.source_practice_ids):
        obj = index[oid]
        strategies[oid] = make('Strategy', 'strategy:' + oid, {
            'name': obj.class_name, 'family': 'iSQD pedagogical practice',
            'rationale': obj.attributes.get('rationale') or 'See original practice in source snapshot.',
            'constraints': constraints}, [oid])
    units = [make('ProcessNode', 'unit:' + str(i), {
        'name': unit.title, 'kind': 'UNIT', 'outcomes': [ref(outcomes[unit.source_target_id])],
        'strategies': [ref(strategies[p]) for p in unit.source_practice_ids]}, [unit.source_target_id])
        for i, unit in enumerate(draft.units)]
    phase = make('ProcessNode', 'phase', {
        'name': draft.title, 'kind': 'PHASE', 'composition': 'SEQUENTIAL',
        'children': [ref(u) for u in units], 'outcomes': [ref(o) for o in outcomes.values()]}, [data.source.root_id])
    design = make('LearningDesign', 'design', {
        'name': draft.title, 'root': ref(phase), 'outcomes': [ref(o) for o in outcomes.values()],
        'strategies': [ref(s) for s in strategies.values()]}, [data.source.root_id])
    artifact = SyllabusArtifact(context_id=root.id, outline=design.ref, source_snapshot=source.ref,
        units=tuple(UnitLink(key=u.key, node=node.ref) for u, node in zip(draft.units, units)),
        draft=draft, review=verdict, revises=revises, revision_reasons=tuple(revision_reasons), edited_by=edited_by)
    syllabus = make('Resource', 'syllabus', {
        'title': ('Curator syllabus draft: ' if edited_by is None else 'Teacher-edited syllabus draft: ') + draft.title,
        'contentOrLocator': encoded(artifact.model_dump(mode='json')),
        'topics': [ref(t) for t in topics.values()], 'outcomes': [ref(o) for o in outcomes.values()],
        'derivedFrom': [ref(source), *(ref(r) for r in corpus)],
        'usageConditions': 'Syllabus authoring payload; approval does not authorize teaching resource use.'},
        [data.source.root_id])
    link = encoded({'format': 'aimpro-syllabus-link', 'format_version': 1, 'syllabus': ref(syllabus)})
    linked_design = design.model_copy(update={'provenance': design.provenance.model_copy(update={
        'sources': [*design.provenance.sources, link]})})
    result[result.index(design)] = linked_design
    domain = make('DomainModel', 'model', {
        'name': draft.title, 'scope': 'Proposed syllabus outline without executable activities; approval and application remain explicit.',
        'topics': [ref(t) for t in topics.values()], 'outcomes': [ref(o) for o in outcomes.values()],
        'definitions': [ref(e) for e in result if e.type not in {'Topic', 'LearningOutcome'}]}, [data.source.root_id])
    updated = root.model_copy(update={'version': uuid4().hex, 'provenance': domain.provenance,
        'fields': {**root.fields, 'models': [*root.fields['models'], ref(domain)], 'learningDesign': ref(linked_design)}})
    result.append(validate_entity(entity_data(updated), context.contract))
    return tuple(result)


def resolve(store, context, design_ref):
    """Resolve only a current outline whose exact syllabus payload was approved/applied."""
    design_ref = EntityRef.model_validate(design_ref)
    root = context.snapshot.context
    if design_ref.type != 'LearningDesign' or root.fields.get('learningDesign') != design_ref.model_dump():
        raise ValueError('Syllabus outline is not the current context design')
    design = context.snapshot.get(design_ref)
    links = []
    for raw in design.provenance.sources:
        try:
            link = json.loads(raw)
        except ValueError:
            continue
        if isinstance(link, dict) and link.get('format') == 'aimpro-syllabus-link':
            if set(link) != {'format', 'format_version', 'syllabus'} or link['format_version'] != 1:
                raise ValueError('Invalid syllabus link format')
            links.append(EntityRef.model_validate(link['syllabus']))
    if len(links) != 1 or links[0].type != 'Resource':
        raise ValueError('Syllabus outline requires one exact payload link')
    approved = resolve_artifact(store, context, links[0])
    if approved.artifact.outline != design_ref:
        raise ValueError('Syllabus payload belongs to another outline')
    return approved


def resolve_artifact(store, context, syllabus_ref):
    """Resolve a pinned syllabus through its original applied candidate closure.

    Callers authorize the owning context and select the Resource explicitly. The
    current composite design need not be the original Curator outline.
    """
    root = context.snapshot.context
    syllabus = store.read(EntityRef.model_validate(syllabus_ref), owner=root.id)
    if syllabus.type != 'Resource':
        raise ValueError('A syllabus Resource is required')
    artifact = SyllabusArtifact.model_validate_json(syllabus.fields['contentOrLocator'])
    design_ref = artifact.outline
    # Only an owning-context applied proposal can supply historical definitions.
    owners = [p for p in store.owned(root.id, 'ChangeProposal')
              if p.fields['status'] == 'APPLIED' and
              syllabus.ref.model_dump() in p.fields['candidateDefinitions']]
    if len(owners) != 1:
        raise ValueError('Syllabus requires one applied owning-context proposal')
    saved = proposal_candidates(store, owners[0])
    snapshot = replace(context.snapshot, entities={**context.snapshot.entities, **{c.ref: c for c in saved}})
    context = replace(context, snapshot=snapshot)
    design = context.snapshot.get(design_ref)
    if (artifact.context_id != root.id or artifact.outline != design_ref or
            artifact.source_snapshot.type != 'Resource' or
            artifact.source_snapshot.model_dump() not in syllabus.fields['derivedFrom']):
        raise ValueError('Syllabus payload belongs to another outline or context')
    source = context.snapshot.get(artifact.source_snapshot)
    data = LeadInput.model_validate_json(source.fields['contentOrLocator'])
    checked_syllabus(data, artifact.draft)
    phase = context.snapshot.get(design.fields['root'])
    if (tuple(u.key for u in artifact.units) != tuple(u.key for u in artifact.draft.units) or
            phase.fields['children'] != [u.node.model_dump() for u in artifact.units] or
            any(u.node.type != 'ProcessNode' for u in artifact.units)):
        raise ValueError('Syllabus unit mapping differs from the reviewed outline')
    matches = []
    for proposal in store.owned(root.id, 'ChangeProposal'):
        if proposal.fields['status'] != 'APPLIED' or design_ref.model_dump() not in proposal.fields['candidateDefinitions']:
            continue
        saved = proposal_candidates(store, proposal)
        if not {syllabus.ref, source.ref} <= {c.ref for c in saved}:
            continue
        # Application does not alter syllabus candidates: require exact active payloads.
        if any(store.read(c.ref, owner=root.id) != c for c in saved):
            raise ValueError('Applied syllabus candidates differ from their reviewed payload')
        decision = store.read(EntityRef.model_validate(proposal.fields['decision']), owner=root.id)
        reviewed = store.read(EntityRef.model_validate(decision.fields['target']), owner=root.id)
        decider = store.read(EntityRef.model_validate(decision.fields['decider']), owner=root.id)
        entities = {**context.snapshot.entities, **{c.ref: c for c in saved},
                    proposal.ref: proposal, reviewed.ref: reviewed, decision.ref: decision, decider.ref: decider}
        if not approval_valid(proposal, replace(context.snapshot, entities=entities), context.policy):
            raise ValueError('Syllabus approval does not cover the exact payload or current authority')
        for change in store.owned(root.id, 'StateChange'):
            cause = EntityRef.model_validate(change.fields['cause'])
            candidate_root = next(c for c in saved if c.type == 'ExecutionContext')
            if (cause.id == proposal.id and change.fields['newVersion'] == candidate_root.version and
                    change.fields['authorizationBasis'] == canonical(decision.ref.model_dump())):
                applied_cause = store.read(cause, owner=root.id)
                if (applied_cause.fields['status'] == 'APPROVED' and
                        review_payload_key(applied_cause, saved) == proposal.fields['reviewPayloadKey']):
                    matches.append((proposal, decision, change))
    if len(matches) != 1:
        raise ValueError('Syllabus requires one valid approved and applied proposal')
    proposal, decision, change = matches[0]
    return ApprovedSyllabus(syllabus=syllabus.ref, artifact=artifact, source=data,
        proposal=proposal.ref, decision=decision.ref, change=change.ref)
