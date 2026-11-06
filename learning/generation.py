"""Reserve exact authoring inputs, generate outside locks, then propose atomically."""

import json
import logging

from aimpro.generators import (ArtifactInput, GenerationCommand, GenerationInput,
    UnitInput, generate)
from aimpro.syllabus_state import resolve_artifact
from aimpro.teacher_contracts import ApprovedReview
from learning.authoring import dependency_findings, review_receipt
from learning.context import LearningRequest
from learning.outputs import LearningResponse
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
    row = store.db.execute('SELECT payload,result FROM requests WHERE id=? AND owner=?',
                           (request_id, context_id)).fetchone()
    if row is None:
        return None
    saved = json.loads(row['payload'])
    if saved.get('identity') != identity or row['result'] is None:
        raise StateConflict('Generation request conflicts or has no confirmed result')
    return LearningResponse.model_validate_json(row['result'])


def generate_project(service, context_id, subject_key, role, command, *, request_id, authoring_factory):
    command = GenerationCommand.model_validate(command)
    identity = {'operation': 'PROJECT_GENERATE_' + role, 'subject_key': subject_key,
                'command': command.model_dump(mode='json')}
    # Authorization, exact snapshot and reservation share one short write lock.
    with service.store.db:
        service.store.db.execute('BEGIN IMMEDIATE')
        context = service._context(context_id, subject_key)
        _authorize(context)
        LearningRequest(request_id=request_id, subject_key=subject_key,
            context_ref=command.base_context, text='Generate a reviewed project artifact', intent='STATE')
        cached = _cached(service.store, request_id, context_id, identity)
        if cached is not None:
            return cached
        data, manifest = resolve_inputs(service, context, role, command)
        payload = canonical({'identity': identity, 'input_snapshot': data.model_dump(mode='json')})
        service.store.db.execute('INSERT INTO requests VALUES (?,?,?,NULL)', (request_id, context_id, payload))
    try:
        dispatcher, lead, budget = authoring_factory()
        draft, verdict = generate(data, dispatcher=dispatcher, lead=lead, max_context_chars=budget)
        from aimpro.generation_state import revision
        bundle = revision(context, manifest, data, draft, verdict)
        with service.store.db:
            service.store.db.execute('BEGIN IMMEDIATE')
            # An administrator may have abandoned the request during generation.
            row = service.store.db.execute('SELECT payload,result FROM requests WHERE id=? AND owner=?',
                                           (request_id, context_id)).fetchone()
            if row is None or row['payload'] != payload or row['result'] is not None:
                raise StateConflict('Generation reservation changed during external work')
            current = service._context(context_id, subject_key)
            _authorize(current)
            pinned, _ = resolve_inputs(service, current, role, command)
            if pinned != data:
                raise StateConflict('Generation input approvals or exact dependencies changed')
            current, selected, candidates = _revision_manifest(service.store, current, bundle)
            proposed = _persist(service, current, selected, candidates, bundle.explanation)
            result = LearningResponse(kind='PROPOSAL', content='Authoring output awaits explicit human review and application.',
                proposal_refs=(proposed.proposal,), application_status='pending')
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        logging.getLogger('agent_system').warning('Project generation failed (%s)', type(error).__name__)
        result = LearningResponse(kind='FAILURE', content='Authoring generation did not complete; no accepted proposal was persisted.')
    try:
        service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
    except StateConflict:
        # Return an explicit administrative abandonment, never resurrect work.
        return _cached(service.store, request_id, context_id, identity)
    return result
