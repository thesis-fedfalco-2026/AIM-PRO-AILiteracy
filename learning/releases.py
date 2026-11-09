"""Production frozen releases, delivery imports and activation proposals.

These synchronous host operations do no model, retrieval or network work. Each
proposing command holds one SQLite write transaction through authorization,
validation, request reservation and the atomic proposal; inspection uses one
read transaction. Decisions and applications remain the generic ALM steps, and
application rechecks the reserved contracts below under its final write lock.
"""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from document_search.contracts import resource_key
from learning.authoring import (ProjectManifest, ReleaseManifest, ReviewReceipt, dependency_findings,
                                released_entities, review_receipt, prepare_release, _exact)
from learning.context import LearningRequest, RunContext, load_context, references
from learning.contracts import EntityRef, Finding, Record, Text, entity_data, make_entity
from learning.decisions import create_proposal, save_proposal
from learning.metamodel import validate_entity
from learning.planning import ROLE_CONTRACTS
from learning.policies import RuleBinding, ScopeGrant, TrustedPolicy
from learning.projects import _authorize, _draft, _project
from learning.store import StateConflict, canonical
from learning.validation import check_readiness


RELEASE_PREFIX = 'authoring-release:'
DELIVERY_PREFIX = 'authoring-delivery:'
POLICY_PREVIEW = 'Proposed trusted local policy configuration: '
HISTORY = ('ActivityOccurrence', 'LearningEvidence', 'LearningState', 'Evaluation')
DELIVERY_FIELDS = ('models', 'learningDesign', 'policies', 'resourceBindings', 'mode', 'status')
COMMANDS = ('PROPOSE_RELEASE', 'PROPOSE_DELIVERY_IMPORT', 'PROPOSE_ACTIVATION')
# Runtime roles an import may configure. ASSESS has none until an assessor-facing
# evaluation adapter exists (G7), so activation stays refused (owner decision D4).
RUNTIME_WORKERS = {'TEACHER': 'lesson-explainer', 'TRAINER': 'guided-practice-coach'}
ROOT = Path(__file__).resolve().parents[1]


class ReleaseCommand(Record):
    base_context: EntityRef
    project: EntityRef
    domain: EntityRef


class ReleaseProposal(Record):
    proposal: EntityRef
    release: EntityRef
    catalogue: EntityRef
    manifest: ReleaseManifest


class ReleasedArtifact(Record):
    resource: EntityRef
    receipt: ReviewReceipt | None = None


class ReleaseInspection(Record):
    release: EntityRef
    manifest: ReleaseManifest
    receipt: ReviewReceipt | None = None
    project_receipt: ReviewReceipt | None = None
    artifacts: tuple[ReleasedArtifact, ...]
    closure: tuple[EntityRef, ...]
    findings: tuple[Finding, ...]


class BindingSelection(Record):
    requirement: EntityRef
    resource: EntityRef
    usage_scope: Text


class DeliveryImport(Record):
    release: EntityRef
    authoring_context: Text
    base_context: EntityRef
    scope_name: Text
    bindings: tuple[BindingSelection, ...] = ()
    completion_handlers: tuple[RuleBinding, ...] = ()


class ImportPreview(Record):
    mode: Text
    status: Text
    scope: Text
    resource_keys: tuple[Text, ...]
    activities: tuple[Text, ...]
    workers: tuple[Text, ...]
    readiness_findings: tuple[Finding, ...]


class ImportProposal(Record):
    proposal: EntityRef
    release: EntityRef
    domain: EntityRef
    design: EntityRef
    runtime_model: EntityRef
    bindings: tuple[EntityRef, ...]
    policy_preview: TrustedPolicy
    preview: ImportPreview


class ActivationCommand(Record):
    base_context: EntityRef


class ActivationProposal(Record):
    proposal: EntityRef
    release: EntityRef
    policy: EntityRef


class ActivationRefused(ValueError):
    """Activation is refused with explicit findings; nothing was reserved or saved."""

    def __init__(self, findings):
        self.findings = tuple(findings)
        super().__init__('Activation refused: ' + ', '.join(sorted({f.code for f in self.findings})))


def _release_id(context_id, project_id):
    return RELEASE_PREFIX + hashlib.sha256(canonical([context_id, project_id]).encode()).hexdigest()


def _reserved(entity):
    """Release Resources and catalogues are reserved by identity and by content."""
    if entity.id.startswith((RELEASE_PREFIX, DELIVERY_PREFIX)):
        return True
    if entity.type != 'Resource':
        return False
    try:
        value = json.loads(entity.fields['contentOrLocator'])
    except ValueError:
        return False
    return isinstance(value, dict) and value.get('format') == 'authoring-release'


def _other_context(store, context, context_id):
    """Load another context for the same trusted subject inside the caller's transaction."""
    root = store.read_context(context_id)
    request = context.request.model_copy(update={'context_ref': root.ref})
    snapshot = load_context(store, request, context.policy, context.contract)
    participant = next((snapshot.get(r) for r in root.fields['participants']
                        if snapshot.get(r).fields['subjectKey'] == request.subject_key), None)
    if participant is None:
        raise ValueError('Subject is not a participant of the authoring context')
    return RunContext(snapshot, context.policy, context.contract, request, participant)


def _history(store, root):
    return bool(root.fields['activityOccurrences'] or root.fields['learningStates'] or
                any(store.owned(root.id, kind) for kind in HISTORY))


def _no_history(store, root):
    if _history(store, root):
        raise ValueError('The destination holds learner history; changing its release requires a reviewed migration')


def _design(entities, design_ref):
    design = entities[EntityRef.model_validate(design_ref)]
    pending, nodes, activities = [entities[EntityRef.model_validate(design.fields['root'])]], [], {}
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(entities[EntityRef.model_validate(r)] for r in node.fields['children'])
        for ref in node.fields['activities']:
            activities[EntityRef.model_validate(ref)] = entities[EntityRef.model_validate(ref)]
    return design, tuple(nodes), tuple(activities.values())


def _role(intent):
    return next((role for role, contract in ROLE_CONTRACTS.items() if contract[1] == intent), None)


def _command(service, context_id, subject_key, operation, command, request_id, build, result_type):
    payload = canonical({'operation': operation, 'subject_key': subject_key,
                         'command': command.model_dump(mode='json')})
    with service.store.write_transaction():
        context = service._context(context_id, subject_key)
        _authorize(context)
        LearningRequest(request_id=request_id, subject_key=subject_key,
            context_ref=command.base_context, text='Release command ' + operation, intent='STATE')
        _exact(command.base_context, 'ExecutionContext')
        if command.base_context.id != context_id:
            raise ValueError('Base context belongs to another context')
        cached = service.store.request_result(request_id, context_id, payload)
        if cached is not None:
            return result_type.model_validate(cached)
        if command.base_context != context.snapshot.context.ref:
            raise StateConflict('Request context is stale')
        service.store.reserve_request(request_id, context_id, payload)
        result = build(service.store, context, command)
        service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result


def _build_release(store, context, command):
    root = context.snapshot.context
    _draft(context)
    _exact(command.project, 'Resource')
    _exact(command.domain, 'DomainModel')
    resource, project = _project(store, context, command.project)
    manifest = prepare_release(store, context, resource, command.domain)
    identity, version = _release_id(root.id, project.project_id), uuid4().hex
    def make(kind, key, fields):
        return validate_entity(entity_data(make_entity(kind, key, fields, version=version,
            origin='GENERATED_PROPOSAL', responsible=context.request.subject_key)), context.contract)
    release = make('Resource', identity, {
        'title': 'Authoring release: ' + project.project_id, 'topics': resource.fields['topics'],
        'contentOrLocator': canonical(manifest.model_dump(mode='json')),
        'derivedFrom': [resource.ref.model_dump()],
        'usageConditions': 'Frozen authoring release; delivery use requires a separate reviewed import and destination bindings.'})
    previous = next((context.snapshot.get(m) for m in root.fields['models'] if m['id'] == identity + ':catalogue'), None)
    catalogue = make('DomainModel', identity + ':catalogue', {
        'name': 'Release catalogue: ' + project.project_id, 'scope': 'Reviewed immutable releases of one authoring project',
        'topics': resource.fields['topics'],
        'definitions': [*(previous.fields['definitions'] if previous else []), release.ref.model_dump()]})
    updated = root.model_copy(update={'version': version, 'provenance': release.provenance,
        'fields': {**root.fields, 'models': [*[m for m in root.fields['models'] if m['id'] != catalogue.id],
                                             catalogue.ref.model_dump()]}})
    candidates = (release, catalogue, updated)
    proposal = create_proposal(context, (root.ref,), candidates,
        'Freeze the exact reviewed project selection as an immutable release. Approval publishes no '
        'delivery, binding, policy or activation. ' + canonical(manifest.model_dump(mode='json')))
    save_proposal(store, context, proposal, candidates)
    return ReleaseProposal(proposal=proposal.ref, release=release.ref, catalogue=catalogue.ref, manifest=manifest)


def propose_release(service, context_id, subject_key, command, request_id):
    return _command(service, context_id, subject_key, 'PROPOSE_RELEASE',
                    ReleaseCommand.model_validate(command), request_id, _build_release, ReleaseProposal)


def _applied_release(store, ref, owner):
    _exact(ref, 'Resource')
    try:
        release = store.read(ref, owner=owner)
    except ValueError:
        raise ValueError('The release is not applied in its authoring context') from None
    if not release.id.startswith(RELEASE_PREFIX):
        raise ValueError('Select an exact release Resource')
    return release


def _closure(store, context, domain):
    found, pending, findings, seen = {}, [domain], [], set()
    while pending:
        ref = pending.pop()
        if ref in seen:
            continue
        seen.add(ref)
        entity = store.read(ref, owner=context.snapshot.context.id)
        if context.contract.entity_types[entity.type]['instanceLayer'] != 'domain_configuration':
            findings.append(Finding(code='RELEASE_EXECUTION_STATE', target=ref.id,
                reason='A release closure cannot contain authoring execution state.'))
            continue
        found[ref] = entity
        pending.extend(references(entity.fields))
    return tuple(sorted(found, key=lambda r: (r.type, r.id, r.version))), findings


def inspect_release(service, context_id, subject_key, release_ref):
    """Report receipts, the exact frozen closure and findings without writes."""
    with service.store.read_transaction():
        store = service.store
        context = service._context(context_id, subject_key)
        _authorize(context)
        resource = _applied_release(store, release_ref, context_id)
        manifest = ReleaseManifest.model_validate_json(resource.fields['contentOrLocator'])
        if manifest.authoring_context != context_id:
            raise ValueError('Release belongs to another authoring context')
        findings = []
        def receipt(entity, code):
            try:
                return review_receipt(store, context, entity)
            except ValueError:
                findings.append(Finding(code=code, target=entity.id,
                    reason='No valid approved and applied proposal in this context covers this exact version.'))
                return None
        release_receipt = receipt(resource, 'RELEASE_UNAPPROVED')
        project_resource = store.read(manifest.project, owner=context_id)
        project_receipt = receipt(project_resource, 'RELEASE_PROJECT_RECEIPT')
        artifacts = tuple(ReleasedArtifact(resource=ref, receipt=receipt(store.read(ref, owner=context_id),
                          'RELEASE_ARTIFACT_RECEIPT')) for ref in manifest.artifacts)
        if project_receipt and manifest.domain.model_dump() not in store.read(
                project_receipt.proposal, owner=context_id).fields['candidateDefinitions']:
            findings.append(Finding(code='RELEASE_DOMAIN_UNREVIEWED', target=manifest.domain.id,
                reason='The release domain was not reviewed with this project revision.'))
        project = ProjectManifest.model_validate_json(project_resource.fields['contentOrLocator'])
        if (project.authoring_context != context_id or project.design != manifest.design or
                tuple(a.resource for a in project.artifacts) != manifest.artifacts):
            findings.append(Finding(code='RELEASE_PIN_MISMATCH', target=resource.id,
                reason='Release pins differ from its reviewed project.'))
        findings.extend(dependency_findings(project))
        closure, closure_findings = _closure(store, context, manifest.domain)
        findings.extend(closure_findings)
        if not {manifest.project, manifest.design, *manifest.artifacts} <= set(closure):
            findings.append(Finding(code='RELEASE_CLOSURE', target=manifest.domain.id,
                reason='The release domain omits its exact project, design or artifacts.'))
        return ReleaseInspection(release=resource.ref, manifest=manifest, receipt=release_receipt,
            project_receipt=project_receipt, artifacts=artifacts, closure=closure, findings=tuple(findings))


def _receipts(store, authoring, release, manifest):
    def proof(ref):
        return review_receipt(store, authoring, store.read(ref, owner=authoring.snapshot.context.id)).model_dump(mode='json')
    return {'release': proof(release), 'project': proof(manifest.project),
            'artifacts': {canonical(r.model_dump()): proof(r) for r in manifest.artifacts}}


def _pins(manifest, pinned):
    """Requirement id -> exact Resource version fixed by the released generated packages."""
    from aimpro.generation_state import GeneratedArtifact
    pins = {}
    for ref in manifest.artifacts:
        try:
            package = GeneratedArtifact.model_validate_json(pinned[ref].fields['contentOrLocator'])
        except ValueError:
            continue
        for item in package.items:
            for requirement, resource in item.materials.items():
                if pins.setdefault(requirement, resource) != resource:
                    raise ValueError('Release packages pin one requirement to different resources')
    return pins


def _workers(context, roles, scope_name, identity, domain):
    from agent_system.config import parse_agent_file
    workers = []
    for role in sorted(roles & RUNTIME_WORKERS.keys()):
        name = RUNTIME_WORKERS[role]
        config = parse_agent_file(ROOT / 'agents' / (name + '.md'))
        if config.category != role.lower() or config.skills or set(config.tools) != {'search_documents'}:
            raise ValueError('Configured worker no longer matches the delivery runtime profile')
        workers.append(validate_entity(entity_data(make_entity('AgentSpecialization',
            identity + ':' + name, {'registryName': name, 'category': ROLE_CONTRACTS[role][0], 'role': role,
            'topics': domain.fields['topics'], 'competenceScope': domain.fields['scope'], 'skills': [],
            'capabilities': [{'capability': 'search_documents', 'accessPath': 'ORCHESTRATOR_RETRIEVAL',
                              'operations': ['read'], 'scope': scope_name,
                              'purpose': 'Use only the exact approved resource versions bound in this delivery.'}],
            'constraints': ['No state changes, approval claims or inferred competency acquisition.']},
            version=uuid4().hex, origin='GENERATED_PROPOSAL', responsible=context.request.subject_key)), context.contract))
    return workers


def _build_import(store, context, command):
    root, policy, subject = context.snapshot.context, context.policy, context.request.subject_key
    _no_history(store, root)
    if root.fields['models'] or root.fields.get('learningDesign') or root.fields['resourceBindings']:
        raise ValueError('The destination already holds a configuration; replacing it requires a reviewed migration')
    _draft(context)
    if command.authoring_context == root.id:
        raise ValueError('A delivery import requires a separate destination context')
    authoring = _other_context(store, context, command.authoring_context)
    _authorize(authoring)
    release = _applied_release(store, command.release, command.authoring_context)
    manifest, definitions = released_entities(store, authoring, release)
    receipts = _receipts(store, authoring, release.ref, manifest)
    pinned = {e.ref: e for e in definitions}
    design, nodes, activities = _design(pinned, manifest.design)
    project = ProjectManifest.model_validate_json(pinned[manifest.project].fields['contentOrLocator'])
    pins = _pins(manifest, pinned)
    generated = {r for a in project.artifacts if a.kind not in {'SOURCE', 'SYLLABUS'}
                 for r in a.definitions if r.type == 'Resource'}
    requirements = {EntityRef.model_validate(r) for a in activities for r in a.fields['resourceRequirements']}
    scope_name = command.scope_name
    if scope_name in policy.scopes:
        raise ValueError('The delivery import requires a new scope name')
    identity = DELIVERY_PREFIX + hashlib.sha256(canonical([root.id, release.id, release.version]).encode()).hexdigest()
    bindings, keys = [], set()
    if len({s.requirement for s in command.bindings}) != len(command.bindings):
        raise ValueError('Select at most one resource per requirement')
    for selection in command.bindings:
        _exact(selection.requirement, 'ResourceRequirement')
        _exact(selection.resource, 'Resource')
        if selection.usage_scope != scope_name:
            raise ValueError('Bindings may use only the new reviewed delivery scope')
        if selection.requirement not in requirements:
            raise ValueError('Binding requirement is not used by the frozen design')
        if pins.get(selection.requirement.id) != selection.resource or selection.resource not in pinned:
            raise ValueError('A binding must use the exact resource version pinned by the release')
        resource = pinned[selection.resource]
        key = resource_key(resource.id, resource.version)
        if resource.ref not in generated and key not in resource.provenance.sources:
            raise ValueError('A WP3 binding needs an exact catalogue resource and version')
        keys.add(key)
        bindings.append(validate_entity(entity_data(make_entity('ResourceBinding', identity + ':binding:' + uuid4().hex, {
            'context': root.ref.model_dump(), 'resource': resource.ref.model_dump(),
            'requirement': selection.requirement.model_dump(), 'usageScope': scope_name,
            'valid': True, 'reviewPayloadKey': 'pending'},
            origin='GENERATED_PROPOSAL', responsible=subject)), context.contract))
    rules = {EntityRef.model_validate(n.fields['completionRule']) for n in nodes if n.fields.get('completionRule')}
    bound = {b.rule for b in policy.rule_bindings}
    handlers = command.completion_handlers
    if (len({h.rule for h in handlers}) != len(handlers) or not {h.rule for h in handlers} <= rules
            or {h.rule for h in handlers} & bound):
        raise ValueError('Completion handlers must bind new, distinct completion rules of the frozen design')
    roles = {_role(a.fields['intent']) for a in activities}
    domain = pinned[manifest.domain]
    workers = _workers(context, roles, scope_name, identity, domain)
    runtime = validate_entity(entity_data(make_entity('DomainModel', identity, {
        'name': 'Delivery runtime configuration', 'scope': 'This delivery of one frozen release only.',
        'topics': domain.fields['topics'],
        'definitions': [release.ref.model_dump(), *(w.ref.model_dump() for w in workers)]},
        version=uuid4().hex, origin='GENERATED_PROPOSAL', responsible=subject)), context.contract)
    participants = sorted(context.snapshot.get(r).fields['subjectKey'] for r in root.fields['participants'])
    preview = policy.model_dump(mode='json')
    preview.update(policy_ref={**preview['policy_ref'], 'version': uuid4().hex},
        scopes={**preview['scopes'], scope_name: ScopeGrant(contexts=[root.id], subjects=participants,
            activities=sorted({a.id for a in activities}), resources=sorted(keys), sources=[],
            operations=['read']).model_dump(mode='json')},
        rule_bindings=[*preview['rule_bindings'], *(h.model_dump(mode='json') for h in handlers)])
    preview = TrustedPolicy.model_validate(preview)
    policy_entity = context.snapshot.get(policy.policy_ref)
    policy_entity = validate_entity(entity_data(policy_entity.model_copy(update={
        'version': preview.policy_ref.version, 'fields': {**policy_entity.fields,
            'sourceScopes': list(dict.fromkeys([*policy_entity.fields['sourceScopes'], scope_name])),
            'permissions': [*policy_entity.fields['permissions'],
                            POLICY_PREVIEW + canonical(preview.model_dump(mode='json'))]},
        'provenance': policy_entity.provenance.model_copy(update={'origin': 'GENERATED_PROPOSAL', 'responsible': subject})})),
        context.contract)
    updated = root.model_copy(update={'version': uuid4().hex, 'fields': {**root.fields,
        'models': [manifest.domain.model_dump(), runtime.ref.model_dump()],
        'learningDesign': manifest.design.model_dump(), 'policies': preview.policy_ref.model_dump(),
        'resourceBindings': [b.ref.model_dump() for b in bindings]}})
    candidates = (*definitions, release, *workers, runtime, policy_entity, *bindings, updated)
    explanation = ('Import the frozen release unchanged into this delivery. Bindings, runtime workers and the '
        'trusted-policy preview need this destination\'s decision; authoring approval grants no destination use. '
        'The context stays PREPARATION/DRAFT. Install the exact approved policy preview before a separate '
        'activation proposal. ' + canonical({'release': release.ref.model_dump(), 'receipts': receipts,
            'scope': scope_name, 'resource_keys': sorted(keys), 'activities': sorted({a.id for a in activities}),
            'workers': [w.fields['registryName'] for w in workers]}))
    proposal = create_proposal(context, (root.ref,), candidates, explanation)
    save_proposal(store, context, proposal, candidates)
    snapshot = replace(context.snapshot, context=updated, findings=(),
        entities={**context.snapshot.entities, **{c.ref: c for c in candidates}})
    readiness = check_readiness(snapshot, manifest.design, 'advance', learner_ref=context.participant.ref,
                                policy=preview, subject_key=subject)
    return ImportProposal(proposal=proposal.ref, release=release.ref, domain=manifest.domain,
        design=manifest.design, runtime_model=runtime.ref, bindings=tuple(b.ref for b in bindings),
        policy_preview=preview, preview=ImportPreview(mode=updated.fields['mode'], status=updated.fields['status'],
            scope=scope_name, resource_keys=tuple(sorted(keys)), activities=tuple(sorted({a.id for a in activities})),
            workers=tuple(w.fields['registryName'] for w in workers), readiness_findings=readiness))


def propose_delivery_import(service, context_id, subject_key, command, request_id):
    return _command(service, context_id, subject_key, 'PROPOSE_DELIVERY_IMPORT',
                    DeliveryImport.model_validate(command), request_id, _build_import, ImportProposal)


def _delivery(context):
    root = context.snapshot.context
    runtime = [context.snapshot.get(m) for m in root.fields['models'] if m['id'].startswith(DELIVERY_PREFIX)]
    if len(runtime) != 1:
        raise ValueError('Activation requires one applied release import')
    releases = [context.snapshot.get(r) for r in runtime[0].fields['definitions'] if r['id'].startswith(RELEASE_PREFIX)]
    if len(releases) != 1:
        raise ValueError('The delivery runtime configuration must pin one release')
    return runtime[0], releases[0], ReleaseManifest.model_validate_json(releases[0].fields['contentOrLocator'])


def activation_findings(store, context):
    """Every condition a LEARNING/ACTIVE proposal for an imported delivery must meet."""
    snapshot, root = context.snapshot, context.snapshot.context
    runtime, release, manifest = _delivery(context)
    findings = []
    try:
        receipt = review_receipt(store, context, release)
        if _recorded(store, root.id, receipt.proposal)[0] != 'PROPOSE_DELIVERY_IMPORT':
            raise ValueError('Release entered the delivery outside the import command')
    except ValueError:
        findings.append(Finding(code='RELEASE_IMPORT_UNAPPLIED', target=release.id,
            reason='No valid applied delivery import in this context covers the release.'))
    if (root.fields.get('learningDesign') != manifest.design.model_dump() or
            manifest.domain.model_dump() not in root.fields['models']):
        findings.append(Finding(code='RELEASE_PIN_MISMATCH', target=root.id,
            reason='The delivery no longer pins the frozen release domain and design.'))
    if _history(store, root):
        findings.append(Finding(code='RELEASE_LEARNER_HISTORY', target=root.id,
            reason='The destination already holds learner history; this requires a reviewed migration.'))
    policy = snapshot.get(root.fields['policies'])
    if POLICY_PREVIEW + canonical(context.policy.model_dump(mode='json')) not in policy.fields['permissions']:
        findings.append(Finding(code='RELEASE_POLICY_NOT_INSTALLED', target=policy.id,
            reason='The installed trusted policy differs from the reviewed import preview.',
            resolution='Install the exact approved policy preview file before activation.'))
    findings.extend(check_readiness(snapshot, manifest.design, 'advance', learner_ref=context.participant.ref,
                                    policy=context.policy, subject_key=context.request.subject_key))
    _, nodes, activities = _design(snapshot.entities, manifest.design)
    for node in nodes:
        rule = node.fields.get('completionRule')
        if rule and EntityRef.model_validate(rule) not in snapshot.rule_bindings:
            findings.append(Finding(code='RELEASE_COMPLETION_HANDLER', target=node.id,
                reason='The completion rule has no explicit handler in the installed trusted policy.'))
    roles = {snapshot.get(r).fields['role'] for r in runtime.fields['definitions'] if r['type'] == 'AgentSpecialization'}
    for activity in activities:
        if _role(activity.fields['intent']) not in roles:
            assess = activity.fields['intent'] == 'ASSESS'
            findings.append(Finding(code='RELEASE_RUNTIME_ROLE', target=activity.id,
                reason=('This ASSESS activity has no configured runtime assessor role; activation stays refused '
                        'until a later explicit decision (D4).') if assess else
                       'This activity intent has no configured runtime role in the delivery.',
                resolution='Keep the delivery in PREPARATION.' if assess else 'Correct the delivery configuration.'))
    return release, tuple(findings)


def _build_activation(store, context, command):
    root = context.snapshot.context
    _draft(context)
    release, findings = activation_findings(store, context)
    if any(f.severity == 'BLOCKING' for f in findings):
        raise ActivationRefused(f for f in findings if f.severity == 'BLOCKING')
    updated = root.model_copy(update={'version': uuid4().hex,
        'fields': {**root.fields, 'mode': 'LEARNING', 'status': 'ACTIVE'}})
    proposal = create_proposal(context, (root.ref,), (updated,),
        'Activate the applied delivery import as LEARNING/ACTIVE. This changes nothing else; the human '
        'decision and the application remain separate steps. ' + canonical({'release': release.ref.model_dump(),
            'policy': root.fields['policies']}))
    save_proposal(store, context, proposal, (updated,))
    return ActivationProposal(proposal=proposal.ref, release=release.ref,
                              policy=EntityRef.model_validate(root.fields['policies']))


def propose_activation(service, context_id, subject_key, command, request_id):
    command = ActivationCommand.model_validate(command)
    root = service.store.read_context(context_id)
    if root.fields['policies'] != service.policy.policy_ref.model_dump():
        raise ActivationRefused((Finding(code='RELEASE_POLICY_NOT_INSTALLED', target=root.fields['policies']['id'],
            reason='The installed trusted policy version differs from the context policy.',
            resolution='Install the exact approved policy preview file before activation.'),))
    return _command(service, context_id, subject_key, 'PROPOSE_ACTIVATION', command, request_id,
                    _build_activation, ActivationProposal)


def _recorded(store, owner, proposal):
    for row in store.recorded_requests(owner):
        payload, result = json.loads(row.payload), json.loads(row.result)
        if (isinstance(payload, dict) and payload.get('operation') in COMMANDS and isinstance(result, dict)
                and isinstance(result.get('proposal'), dict) and result['proposal'].get('id') == proposal.id):
            return payload['operation'], payload['command']
    raise ValueError('Releases, delivery imports and their activation require the dedicated commands')


def _foreign_projects(entities, root):
    """Project domains in this context's models that another authoring context owns."""
    found = set()
    for ref in root.fields['models']:
        if not ref['id'].startswith('authoring-project:'):
            continue
        model = entities.get(EntityRef.model_validate(ref))
        projects = [entities.get(EntityRef.model_validate(r)) for r in (model.fields['definitions'] if model else [])
                    if r['type'] == 'Resource' and r['id'] + ':model' == ref['id']]
        if (model is None or len(projects) != 1 or projects[0] is None or
                ProjectManifest.model_validate_json(projects[0].fields['contentOrLocator']).authoring_context != root.id):
            found.add(EntityRef.model_validate(ref))
    return found


def _reserved_change(context, candidates):
    root = context.snapshot.context
    updated = next((c for c in candidates if c.type == 'ExecutionContext'), root)
    entities = {**context.snapshot.entities, **{c.ref: c for c in candidates}}
    def entries(value):
        return [r for r in value.fields['models'] if r['id'].startswith((RELEASE_PREFIX, DELIVERY_PREFIX))]
    imported = any(r['id'].startswith(DELIVERY_PREFIX) for r in root.fields['models'])
    return (any(_reserved(c) for c in candidates) or entries(root) != entries(updated) or
            bool(_foreign_projects(entities, updated) - _foreign_projects(entities, root)) or
            imported and any(root.fields.get(k) != updated.fields.get(k) for k in DELIVERY_FIELDS))


def refuse_generic(context, candidates):
    """Generic proposals cannot create releases, import them or activate an imported delivery."""
    if _reserved_change(context, candidates):
        raise ValueError('Releases, delivery imports and their activation require the dedicated commands')


def validate_release_application(store, context, proposal, candidates):
    """Recheck reserved release, import and activation contracts under the application lock."""
    if not _reserved_change(context, candidates):
        return
    root = context.snapshot.context
    operation, command = _recorded(store, root.id, proposal)
    _authorize(context)
    updated = next((c for c in candidates if c.type == 'ExecutionContext'), root)
    if operation == 'PROPOSE_RELEASE':
        command = ReleaseCommand.model_validate(command)
        _draft(context)
        resource, _ = _project(store, context, command.project)
        manifest = prepare_release(store, context, resource, command.domain)
        releases = [c for c in candidates if c.type == 'Resource' and c.id.startswith(RELEASE_PREFIX)]
        if len(releases) != 1 or ReleaseManifest.model_validate_json(releases[0].fields['contentOrLocator']) != manifest:
            raise ValueError('Release differs from its exact host-validated manifest')
    elif operation == 'PROPOSE_DELIVERY_IMPORT':
        command = DeliveryImport.model_validate(command)
        _draft(context)
        _no_history(store, root)
        if root.fields['models'] or root.fields['resourceBindings']:
            raise ValueError('The destination already holds a configuration; replacing it requires a reviewed migration')
        authoring = _other_context(store, context, command.authoring_context)
        _authorize(authoring)
        release = store.read(command.release, owner=command.authoring_context)
        _, definitions = released_entities(store, authoring, release)
        supplied = {c.ref: entity_data(c) for c in candidates}
        if (any(supplied.get(e.ref) != entity_data(e) for e in definitions) or
                (updated.fields['mode'], updated.fields['status']) != ('PREPARATION', 'DRAFT')):
            raise ValueError('Import must keep the frozen definitions unchanged and the delivery in PREPARATION')
    else:
        _, findings = activation_findings(store, context)
        if any(f.severity == 'BLOCKING' for f in findings):
            raise ActivationRefused(f for f in findings if f.severity == 'BLOCKING')
        changed = {k for k in root.fields.keys() | updated.fields.keys() if root.fields.get(k) != updated.fields.get(k)}
        if changed - {'mode', 'status'} or (updated.fields['mode'], updated.fields['status']) != ('LEARNING', 'ACTIVE'):
            raise ValueError('Activation changes only mode and status to LEARNING/ACTIVE')
