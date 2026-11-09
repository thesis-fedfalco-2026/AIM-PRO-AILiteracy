"""Prepare local worker, policy and progression configuration for human review."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from agent_system.config import parse_agent_file
from agent_system.registry import AgentRegistry
from document_search.contracts import resource_key
from learning.contracts import EntityRef, entity_data, make_entity
from learning.decisions import approval_valid, create_proposal, save_proposal
from learning.metamodel import validate_entity
from learning.planning import eligible_specializations
from learning.policies import RuleBinding, ScopeGrant, authorize, scope_allows
from learning.rules import all_completed
from learning.store import canonical
from learning.validation import check_readiness


WORKERS = {'lesson-explainer': 'TEACHER', 'guided-practice-coach': 'TRAINER'}
ROOT = Path(__file__).resolve().parents[1]


def prepare_execution(store, context, *, learner, scope_name=None, base_dir=ROOT):
    root, policy = context.snapshot.context, context.policy
    subject = context.request.subject_key
    authorize(policy, subject, 'propose', root.ref)
    if (root.fields['mode'], root.fields['status']) != ('PREPARATION', 'DRAFT'):
        raise ValueError('Execution setup requires PREPARATION DRAFT')
    if not root.fields.get('learningDesign'):
        raise ValueError('Apply a reviewed teaching design before preparing execution')
    if root.fields['activityOccurrences'] or root.fields['learningStates']:
        raise ValueError('Existing learner history requires an explicit configuration migration')
    people = [context.snapshot.get(r) for r in root.fields['participants']]
    person = next((p for p in people if p.fields['subjectKey'] == learner), None)
    if (person is None or 'LEARNER' not in person.fields['roles'] or learner not in policy.subjects
            or set(policy.subjects[learner].roles) != {'LEARNER'}):
        raise ValueError('Select an existing learner-only policy subject and participant')
    scope_name = scope_name if scope_name is not None else 'learning-' + root.id
    if (not isinstance(scope_name, str) or not scope_name.strip() or scope_name != scope_name.strip()
            or scope_name in policy.scopes):
        raise ValueError('Execution setup requires a new context-specific learning scope name')
    design = context.snapshot.get(root.fields['learningDesign'])
    models = [context.snapshot.get(r) for r in root.fields['models']]
    owners = [m for m in models if design.ref.model_dump() in m.fields['definitions']]
    if len(owners) != 1:
        raise ValueError('The teaching design must have one direct owning model')
    model = owners[0]
    pending = [context.snapshot.get(design.fields['root'])]
    nodes, activities = {}, {}
    while pending:
        node = pending.pop()
        if node.ref in nodes:
            raise ValueError('Shared or cyclic process nodes require explicit setup')
        nodes[node.ref] = node
        pending.extend(context.snapshot.get(r) for r in node.fields['children'])
        for ref in node.fields['activities']:
            activity = context.snapshot.get(ref)
            activities[activity.ref] = activity
    if not activities:
        raise ValueError('Execution setup requires concrete learning activities')
    if any(a.fields['intent'] not in {'EXPLAIN', 'PRACTICE'} for a in activities.values()):
        raise ValueError('Activity intents are not covered by the proposed Teacher/Trainer roles; review them or explicitly configure other roles')
    if any(n.fields.get('completionRule') for n in nodes.values()) or any(
        context.snapshot.get(r).type == 'AgentSpecialization' for r in model.fields['definitions']
    ):
        raise ValueError('Existing execution configuration requires an explicit revision')
    original_bindings = [context.snapshot.get(r) for r in root.fields['resourceBindings']]
    selected = {}
    for activity in activities.values():
        for requirement in activity.fields['resourceRequirements']:
            required = context.snapshot.get(requirement)
            matches = [b for b in original_bindings if b.fields.get('requirement') == requirement
                       and b.fields['valid'] and approval_valid(b, context.snapshot, policy)
                       and scope_allows(policy, b.fields['usageScope'], root.id, subject, (activity.id,))]
            if required.fields['mandatory'] and not matches:
                raise ValueError('Every mandatory requirement needs a currently approved binding')
            for binding in matches:
                source = context.snapshot.get(binding.fields['resource'])
                if resource_key(source.id, source.version) not in source.provenance.sources:
                    raise ValueError('Learning retrieval requires an exact corpus resource identity/version')
                selected[binding.ref] = binding
    if not selected:
        raise ValueError('No approved corpus resource binding is available')
    candidates = []

    def checked(entity):
        entity = validate_entity(entity_data(entity), context.contract)
        candidates.append(entity)
        return entity

    def make(kind, identity, fields):
        return checked(make_entity(kind, identity, fields, origin='GENERATED_PROPOSAL', responsible=subject))

    prefix = 'execution-' + uuid4().hex
    rules = {}
    revised_nodes = {ref: node.model_copy(update={'version': uuid4().hex}) for ref, node in nodes.items()}
    for ref, node in nodes.items():
        children = node.fields['children'] if node.fields['kind'] == 'PHASE' else node.fields['activities']
        rule = make('RuleDefinition', prefix + ':completion:' + node.id, {
            'purpose': 'Complete this process node only when every direct child is explicitly COMPLETED.',
            'inputs': [r['id'] for r in children],
            'condition': 'Every direct child status equals COMPLETED; SKIPPED does not count as completed.',
            'outcome': 'Process completion only. This rule does not assign acquisition, a grade or verification.',
            'unknownBehavior': 'Missing or unrecognized statuses remain UNKNOWN; do not infer completion.',
            'approvalRequirement': 'Human-reviewed configuration and actual recorded child completion; a submission alone is insufficient.'})
        rules[rule.ref] = all_completed
        revised = revised_nodes[ref]
        revised = revised.model_copy(update={'fields': {**revised.fields,
            'children': [revised_nodes[EntityRef.model_validate(r)].ref.model_dump() for r in node.fields['children']],
            'completionRule': rule.ref.model_dump()}})
        revised_nodes[ref] = checked(revised)
    profiles = []
    for name, role in WORKERS.items():
        config = parse_agent_file(Path(base_dir) / 'agents' / (name + '.md'))
        if config.category != role.lower() or config.skills or set(config.tools) != {'search_documents'}:
            raise ValueError('Configured worker no longer matches the proposed execution profile')
        profiles.append(make('AgentSpecialization', prefix + ':' + name, {
            'registryName': name, 'category': 'TEACHER_TRAINER', 'role': role,
            'topics': model.fields['topics'], 'competenceScope': model.fields['scope'], 'skills': [],
            'capabilities': [{'capability': 'search_documents', 'accessPath': 'ORCHESTRATOR_RETRIEVAL',
                              'operations': ['read'], 'scope': scope_name,
                              'purpose': 'Use only the exact approved resource versions for this workshop.'}],
            'constraints': ['No state changes, approval claims or inferred competency acquisition.',
                            'Respect fictional customer data and the approved source constraints.']}))
    policy_ref = policy.policy_ref.model_copy(update={'version': uuid4().hex})
    next_policy = policy.model_copy(deep=True)
    next_policy = next_policy.model_copy(update={'policy_ref': policy_ref, 'scopes': {**next_policy.scopes,
        scope_name: ScopeGrant(contexts=[root.id], subjects=list(dict.fromkeys([subject, learner])),
            activities=sorted(a.id for a in activities.values()),
            resources=sorted({resource_key(b.fields['resource']['id'], b.fields['resource']['version']) for b in selected.values()}),
            sources=[], operations=['read'])},
        'rule_bindings': [*next_policy.rule_bindings, *(RuleBinding(rule=ref, handler='all_completed') for ref in rules)]})
    grant = next_policy.subjects[learner]
    next_policy.subjects[learner] = grant.model_copy(update={'actions': {**grant.actions,
        root.id: list(dict.fromkeys([*grant.actions.get(root.id, []), 'read', 'interact', 'submit']))}})
    next_policy = type(policy).model_validate(next_policy.model_dump(mode='json'))
    policy_entity = context.snapshot.get(policy.policy_ref)
    checked(policy_entity.model_copy(update={'version': policy_ref.version, 'fields': {**policy_entity.fields,
        'sourceScopes': list(dict.fromkeys([*policy_entity.fields['sourceScopes'], scope_name])),
        'permissions': [*policy_entity.fields['permissions'],
                        'Proposed trusted local policy configuration: ' + canonical(next_policy.model_dump(mode='json'))]},
        'provenance': policy_entity.provenance.model_copy(update={'origin': 'GENERATED_PROPOSAL', 'responsible': subject})}))
    binding_refs = {}
    for ref, binding in selected.items():
        fields = {k: v for k, v in binding.fields.items() if k != 'approvalDecision'}
        fields.update(usageScope=scope_name, reviewPayloadKey='pending')
        revised = checked(binding.model_copy(update={'version': uuid4().hex, 'fields': fields,
            'provenance': binding.provenance.model_copy(update={'origin': 'GENERATED_PROPOSAL', 'responsible': subject})}))
        binding_refs[ref] = revised.ref
    revised_design = checked(design.model_copy(update={'version': uuid4().hex, 'fields': {
        **design.fields, 'root': revised_nodes[EntityRef.model_validate(design.fields['root'])].ref.model_dump()}}))
    replacements = {**{ref: node.ref for ref, node in revised_nodes.items()}, design.ref: revised_design.ref}
    revised_model = checked(model.model_copy(update={'version': uuid4().hex, 'fields': {**model.fields,
        'definitions': [replacements.get(EntityRef.model_validate(r), EntityRef.model_validate(r)).model_dump()
                        for r in model.fields['definitions']] +
                       [e.ref.model_dump() for e in candidates if e.type in {'RuleDefinition', 'AgentSpecialization'}]}}))
    revised_root = checked(root.model_copy(update={'version': uuid4().hex, 'fields': {**root.fields,
        'models': [revised_model.ref.model_dump() if EntityRef.model_validate(r) == model.ref else r for r in root.fields['models']],
        'learningDesign': revised_design.ref.model_dump(), 'policies': policy_ref.model_dump(),
        'resourceBindings': [binding_refs.get(EntityRef.model_validate(r), EntityRef.model_validate(r)).model_dump()
                             for r in root.fields['resourceBindings']]}}))
    explanation = ('Prepare context-specific learner resource permissions, Teacher/Trainer specializations and '
        'conservative child-completion rules. The context stays PREPARATION/DRAFT. Changed binding scopes '
        'require fresh approval; old decisions do not cover them. Review the complete trusted policy preview. '
        'After approved application, use that exact new policy file; activation is a separate reviewed action.')
    proposal = create_proposal(context, (root.ref,), tuple(candidates), explanation)
    preview = replace(context.snapshot, context=revised_root,
        entities={**context.snapshot.entities, **{e.ref: e for e in candidates}},
        rule_bindings={**context.snapshot.rule_bindings, **rules}, findings=())
    registry = AgentRegistry([parse_agent_file(Path(base_dir) / 'agents' / (name + '.md')) for name in WORKERS])
    names = [e.fields['registryName'] for e in eligible_specializations(preview, registry, next_policy)]
    if set(names) != set(WORKERS) or len(names) != len(WORKERS):
        raise ValueError('Prepared specializations do not match the actual worker registry')
    with store.write_transaction():
        if store.read_context(root.id).version != root.version:
            raise ValueError('Context changed during execution setup')
        save_proposal(store, context, proposal, tuple(candidates))
    return {'proposal': entity_data(proposal), 'policy_preview': next_policy.model_dump(mode='json'),
            'preview': {'mode': revised_root.fields['mode'], 'status': revised_root.fields['status'],
                        'eligible_workers': sorted(names), 'resource_keys': next_policy.scopes[scope_name].resources,
                        'learning_source_scopes': next_policy.scopes[scope_name].sources,
                        'readiness_findings': [f.model_dump() for f in check_readiness(preview, revised_design.ref, 'advance',
                            learner_ref=person.ref, policy=next_policy, subject_key=learner)]}}
