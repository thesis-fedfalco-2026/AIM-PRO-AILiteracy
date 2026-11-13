"""Reserve exact authoring inputs, generate outside locks, then propose atomically."""

import hashlib
import json
import logging

from aimpro.generators import (CONTRACTS, DISPATCH, NOT_ACCEPTED, ArtifactInput, GenerationAttempt, GenerationCommand,
    GenerationInput, GenerationResult, UnitInput, generate)
from aimpro.lead import ReviewError
from aimpro.syllabus_state import resolve_artifact
from aimpro.teacher_contracts import ApprovedReview, RecordedTeacherOutput
from learning.authoring import dependency_findings, review_receipt
from learning.context import LearningRequest
from learning.projects import (_authorize, _coverage, _draft, _persist, _project,
                               _revision_manifest)
from learning.store import StateConflict, canonical


def resolve_inputs(service, context, role, command):
    """Resolve the production project boundary inside the caller's transaction."""
    if command.base_context != context.snapshot.context.ref:
        raise StateConflict('Generation context is stale or foreign')
    _draft(context)
    resource, manifest = _project(service.store, context, command.project)
    receipt = review_receipt(service.store, context, resource)
    syllabuses = [a for a in manifest.artifacts if a.kind == 'SYLLABUS']
    stale = {f.target for f in dependency_findings(manifest)}
    if len(syllabuses) != 1 or syllabuses[0].key in stale:
        raise ValueError('Generation requires one fresh selected syllabus')
    _coverage(service.store, context, syllabuses[0])
    syllabus = resolve_artifact(service.store, context, syllabuses[0].resource)
    if command.teacher_plan is not None and role != 'TEACHER_CONTENT':
        raise ValueError('A structured Teacher plan requires Teacher authoring')
    if role == 'ASSESSMENT' and (command.assessments or command.shared_content):
        raise ValueError('Assessment authoring takes the syllabus and explicit requirements only')
    if role == 'TEACHER_CONTENT' and command.shared_content:
        raise ValueError('Shared Teacher content is an explicit Trainer input')
    inputs = []
    for refs, kind in ((command.assessments, 'ASSESSMENT'), (command.shared_content, 'TEACHER_CONTENT')):
        for ref in refs:
            selection = next((a for a in manifest.artifacts if a.resource == ref and a.kind == kind), None)
            if selection is None or selection.key in stale:
                raise ValueError('Generation input must be an exact fresh selected artifact of the required kind')
            approval = _coverage(service.store, context, selection)
            review = None
            if command.teacher_plan is not None:
                decision = service.store.read(approval.decision, owner=context.snapshot.context.id)
                review = ApprovedReview(artifact=ref, decision=decision.ref,
                    reviewed_target=decision.fields['target'],
                    reviewed_payload_key=decision.fields['reviewedPayloadKey'],
                    reason=decision.fields['reason'])
            inputs.append(ArtifactInput(selection=selection, receipt=approval,
                resource=context.snapshot.get(ref),
                definitions=tuple(context.snapshot.get(r) for r in selection.definitions),
                approved_review=review))
    # Relevant assessments cannot be silently omitted from the model task. All
    # selected assessments intersecting the role's syllabus units are required.
    units = tuple(UnitInput(key=u.key, node=context.snapshot.get(u.node)) for u in syllabus.artifact.units)
    target_outcomes = {canonical(r) for u, d in zip(units, syllabus.artifact.draft.units)
                       if role == 'ASSESSMENT' or {'TEACHER_CONTENT': 'EXPLAIN', 'TRAINER_CONTENT': 'PRACTICE'}[role] in d.planned_intents
                       for r in u.node.fields['outcomes']}
    if role != 'ASSESSMENT':
        relevant = {a.resource for a in manifest.artifacts if a.kind == 'ASSESSMENT' and any(
            e.type == 'AssessmentSpecification' and target_outcomes & {canonical(r) for r in e.fields['outcomes']}
            for e in (context.snapshot.get(r) for r in a.definitions))}
        if not relevant or set(command.assessments) != relevant:
            raise ValueError('Content authoring requires all relevant exact selected approved assessments')
        assessment_coverage = {canonical(r) for a in inputs if a.selection.kind == 'ASSESSMENT'
                               for e in a.definitions if e.type == 'AssessmentSpecification'
                               for r in e.fields['outcomes']}
        if not target_outcomes <= assessment_coverage:
            raise ValueError('Approved assessments do not cover the requested syllabus outcomes')
    constraints = []
    for obj in syllabus.source.source.objects:
        if (obj.package, obj.class_name) == ('iSQD', 'LearningTask'):
            raw = obj.attributes.get('constraints', [])
            constraints.extend(raw if isinstance(raw, list) else [raw])
    data = GenerationInput(role=role, command=command, project_receipt=receipt, syllabus=syllabus,
        units=units, inputs=tuple(inputs), constraints=tuple(constraints))
    if command.teacher_plan is not None:
        from aimpro.teacher import validate_plan
        validate_plan(data)
    if not data.target_units:
        raise ValueError('Syllabus has no units for this authoring intent')
    return data, manifest


def _cached(store, request_id, context_id, identity):
    row = store.request_record(request_id, context_id)
    if row is None:
        return None
    saved = json.loads(row.payload)
    if saved.get('identity') != identity or row.result is None:
        raise StateConflict('Generation request conflicts or has no confirmed result')
    return GenerationResult.model_validate_json(row.result)


def _recorded_origin(store, context_id, recorded, identity, snapshot):
    """Reused text must come from a failed request over the same command and exact inputs."""
    row = store.request_record(recorded.request_id, context_id)
    saved = json.loads(row.payload) if row is not None else {}
    origin = {k: v for k, v in identity.items() if k != 'recorded_teacher'}
    if (row is None or row.result is None or saved.get('identity') != origin or
            canonical(saved.get('input_snapshot')) != canonical(snapshot) or
            GenerationResult.model_validate_json(row.result).kind != 'FAILURE'):
        raise StateConflict('Recorded Teacher output has no matching failed origin request')


class KeptBlocks:
    """The blocks of units a subject's requests accepted, kept for a later request over the same exact inputs (S09d).

    A block is recorded in the ALM requests store under an id derived from its exact input (the request's input
    and its block, whose digest names the command and its base context) and the accepted drafts of the blocks
    before it, so it is reused only when everything it was written from is unchanged. Its result is the draft and
    its accepting attempt; it is written once, outside the request's reservation, and never changes.
    """

    def __init__(self, store, context_id, subject_key):
        self.store, self.context_id, self.subject_key = store, context_id, subject_key

    def _identity(self, part, previous):
        key = hashlib.sha256(canonical({'input_digest': part.digest, 'subject_key': self.subject_key,
            'previous': [d.model_dump(mode='json') for d in previous]}).encode()).hexdigest()
        return 'generation-block:' + key, canonical({'identity': {'operation': 'PROJECT_GENERATE_BLOCK',
            'subject_key': self.subject_key, 'role': part.role, 'block': key}})

    def accepted(self, part, previous):
        request_id, payload = self._identity(part, previous)
        with self.store.read_transaction():
            row = self.store.request_record(request_id, self.context_id)
        if row is None or row.payload != payload or row.result is None:
            return None
        saved = json.loads(row.result)
        draft = CONTRACTS[DISPATCH[part.role]][1].model_validate(saved['draft'])
        return draft, GenerationAttempt.model_validate(saved['attempt'])

    def keep(self, part, previous, draft, attempt):
        request_id, payload = self._identity(part, previous)
        with self.store.write_transaction():
            if self.store.request_record(request_id, self.context_id) is not None:
                return
            self.store.reserve_request(request_id, self.context_id, payload)
            self.store.finish_request(request_id, self.context_id, {
                'draft': draft.model_dump(mode='json'), 'attempt': attempt.model_dump(mode='json')})


def generate_project(service, context_id, subject_key, role, command, *, request_id, authoring_factory,
                     recorded=None):
    command = GenerationCommand.model_validate(command)
    identity = {'operation': 'PROJECT_GENERATE_' + role, 'subject_key': subject_key,
                'command': command.model_dump(mode='json')}
    if recorded is not None:
        recorded = RecordedTeacherOutput.model_validate(recorded)
        identity['recorded_teacher'] = {'request_id': recorded.request_id, 'sha256': recorded.sha256}
    # Authorization, exact snapshot and reservation share one short write lock.
    with service.store.write_transaction():
        context = service._context(context_id, subject_key)
        _authorize(context)
        LearningRequest(request_id=request_id, subject_key=subject_key,
            context_ref=command.base_context, text='Generate a reviewed project artifact', intent='STATE')
        cached = _cached(service.store, request_id, context_id, identity)
        if cached is not None:
            return cached
        data, manifest = resolve_inputs(service, context, role, command)
        saved = {'identity': identity, 'input_snapshot': data.model_dump(mode='json')}
        if recorded is not None:
            _recorded_origin(service.store, context_id, recorded, identity, saved['input_snapshot'])
            saved['recorded_teacher_text'] = recorded.text
        payload = canonical(saved)
        service.store.reserve_request(request_id, context_id, payload)
    attempts = ()
    try:
        dispatcher, lead, budget = authoring_factory()
        draft, verdict, attempts, accepted = generate(data, dispatcher=dispatcher, lead=lead, max_context_chars=budget,
                                            recorded_text=None if recorded is None else recorded.text,
                                            kept=KeptBlocks(service.store, context_id, subject_key))
        if not accepted:
            logging.getLogger('agent_system').warning('Generated content proposed without the review agent\'s acceptance')
        from aimpro.generation_state import revision
        bundle = revision(context, manifest, data, draft, verdict)
        with service.store.write_transaction():
            # An administrator may have abandoned the request during generation.
            row = service.store.request_record(request_id, context_id)
            if row is None or row.payload != payload or row.result is not None:
                raise StateConflict('Generation reservation changed during external work')
            current = service._context(context_id, subject_key)
            _authorize(current)
            pinned, _ = resolve_inputs(service, current, role, command)
            if pinned != data:
                raise StateConflict('Generation input approvals or exact dependencies changed')
            current, selected, candidates = _revision_manifest(service.store, current, bundle)
            proposed = _persist(service, current, selected, candidates, bundle.explanation)
            result = GenerationResult(kind='PROPOSAL', content='Authoring output awaits explicit human review and application.',
                proposal_refs=(proposed.proposal,), application_status='pending', attempts=attempts,
                notice=None if accepted else NOT_ACCEPTED)
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        # ReviewError messages are fixed application text, never model or course content: the author may read them.
        reason = f' ({error})' if isinstance(error, ReviewError) else ''
        logging.getLogger('agent_system').warning('Project generation failed (%s)%s', type(error).__name__, reason)
        result = GenerationResult(kind='FAILURE', attempts=getattr(error, 'attempts', attempts),
            content=f'Authoring generation did not complete{reason}; no accepted proposal was persisted.')
    try:
        service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
    except StateConflict:
        # Return an explicit administrative abandonment, never resurrect work.
        return _cached(service.store, request_id, context_id, identity)
    return result


# The operations of the project generators, whose drafts the review agent judged (S09c).
OPERATIONS = frozenset('PROJECT_GENERATE_' + role for role in ('ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'))


def generation_request(service, context_id, subject_key, request_id):
    """The subject's ended project generation request under ``request_id``, with its attempts; ``None`` otherwise."""
    with service.store.read_transaction():
        context = service._context(context_id, subject_key)
        _authorize(context)
        row = service.store.request_record(request_id, context_id)
    if row is None or row.result is None:
        return None
    identity = json.loads(row.payload).get('identity', {})
    if identity.get('operation') not in OPERATIONS or identity.get('subject_key') != subject_key:
        return None
    return GenerationResult.model_validate_json(row.result)
