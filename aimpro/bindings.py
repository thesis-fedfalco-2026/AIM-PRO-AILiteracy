"""Prepare explicit corpus bindings as a fresh, unapproved teaching proposal."""

from uuid import uuid4

from learning.contracts import EntityRef, Record, Text, make_entity
from learning.decisions import create_proposal, proposal_candidates, review_payload_key, save_proposal
from learning.policies import authorize, scope_allows
from learning.store import canonical
from document_search.contracts import resource_key


class BindingSelection(Record):
    activity: EntityRef
    requirement: EntityRef
    resource: EntityRef
    usage_scope: Text


def propose_bindings(store, context, teaching_proposal, selections):
    root = context.snapshot.context
    subject = context.request.subject_key
    authorize(context.policy, subject, 'propose', root.ref)
    if (root.fields['mode'], root.fields['status']) != ('PREPARATION', 'DRAFT'):
        raise ValueError('Binding preparation requires PREPARATION DRAFT')
    source = store.read(EntityRef.model_validate(teaching_proposal), owner=root.id)
    if (source.type != 'ChangeProposal' or source.fields['context']['id'] != root.id or
            source.fields['baseContextVersion'] != root.version):
        raise ValueError('Teaching proposal belongs to another or stale context')
    latest = next(e for e in store.owned(root.id, 'ChangeProposal') if e.id == source.id)
    if latest.fields['status'] != 'AWAITING_DECISION':
        raise ValueError('Select a pending teaching proposal')
    original = proposal_candidates(store, source)
    if review_payload_key(source, original) != source.fields['reviewPayloadKey']:
        raise ValueError('Teaching candidate payload changed')
    index = {e.ref: e for e in original}
    revised_root = next((e for e in original if e.type == 'ExecutionContext' and e.id == root.id), None)
    if (revised_root is None or (revised_root.fields['mode'], revised_root.fields['status']) != ('PREPARATION', 'DRAFT')
            or not any(e.type == 'LearningDesign' for e in original)):
        raise ValueError('Pending teaching candidates must preserve PREPARATION DRAFT')
    selected = tuple(BindingSelection.model_validate(s) for s in selections)
    if not selected or len(set(s.model_dump_json() for s in selected)) != len(selected):
        raise ValueError('Explicit unique resource selections are required')
    bindings = []
    for selection in selected:
        activity = index.get(selection.activity)
        requirement = index.get(selection.requirement)
        resource = index.get(selection.resource)
        if (activity is None or activity.type != 'ActivityDefinition' or requirement is None
                or requirement.type != 'ResourceRequirement' or resource is None or resource.type != 'Resource'
                or selection.requirement.model_dump() not in activity.fields['resourceRequirements']):
            raise ValueError('Selection must link exact candidates and an activity requirement')
        key = resource_key(resource.id, resource.version)
        if key not in resource.provenance.sources or selection.usage_scope not in resource.provenance.sources:
            raise ValueError('Select an exact versioned corpus source, not a generated asset')
        if not scope_allows(context.policy, selection.usage_scope, root.id, subject, (activity.id,)):
            raise ValueError('Resource usage scope is not authorized for this selection')
        binding = make_entity('ResourceBinding', 'binding-' + uuid4().hex, {
            'context': root.ref.model_dump(), 'resource': resource.ref.model_dump(),
            'requirement': requirement.ref.model_dump(), 'usageScope': selection.usage_scope,
            'valid': True, 'reviewPayloadKey': 'pending'}, origin='GENERATED_PROPOSAL', responsible=subject)
        binding = binding.model_copy(update={'provenance': binding.provenance.model_copy(update={
            'sources': [canonical(source.ref.model_dump()), key],
            'rationale': 'Explicit corpus selection proposed for a fresh human review; not an approval.'})})
        bindings.append(binding)
    revised_root = revised_root.model_copy(update={'version': uuid4().hex, 'fields': {
        **revised_root.fields, 'resourceBindings': [*revised_root.fields['resourceBindings'],
                                                 *(b.ref.model_dump() for b in bindings)]}})
    candidates = tuple(revised_root if e.type == 'ExecutionContext' else e for e in original) + tuple(bindings)
    explanation = ('Proposed teaching design and explicit corpus-resource selections for a new human review. '
        'The original pending proposal is unchanged; its approval, if any, does not cover this new payload. '
        'No activation or learner permission is granted. ' + canonical({
            'source_proposal': source.ref.model_dump(), 'selections': [s.model_dump(mode='json') for s in selected],
            'source_explanation': source.fields['proposedChange']}))
    proposal = create_proposal(context, (root.ref,), candidates, explanation)
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        if store.read_context(root.id).version != root.version:
            raise ValueError('Context changed during binding preparation')
        current = next(e for e in store.owned(root.id, 'ChangeProposal') if e.id == source.id)
        if current.fields['status'] != 'AWAITING_DECISION' or current.fields['reviewPayloadKey'] != source.fields['reviewPayloadKey']:
            raise ValueError('Teaching proposal changed during binding preparation')
        save_proposal(store, context, proposal, candidates)
    return proposal
