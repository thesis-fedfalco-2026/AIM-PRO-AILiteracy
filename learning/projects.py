"""Production authoring selections over the existing ALM review lifecycle.

These synchronous host operations do no model/retrieval work. Reservation,
validated candidates and replay result share one SQLite write transaction.
"""

from dataclasses import replace
import hashlib
from uuid import uuid4

from pydantic import Field

from aimpro.syllabus_state import resolve_artifact
from learning.authoring import (ArtifactSelection, ProjectManifest, ReviewReceipt,
                                dependency_findings, review_receipt, _exact)
from learning.context import LearningRequest, references
from learning.contracts import Entity, EntityRef, Finding, Record, Text, make_entity, entity_data
from learning.decisions import create_proposal, save_proposal, proposal_candidates
from learning.metamodel import validate_entity
from learning.policies import authorize
from learning.store import StateConflict, canonical


REQUIRED_KINDS = ('SOURCE', 'SYLLABUS', 'ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT')


class ProjectInitialization(Record):
    project_id: Text
    base_context: EntityRef
    syllabus: EntityRef


class ProjectRevision(Record):
    project: EntityRef
    base_context: EntityRef
    design: EntityRef
    artifacts: tuple[ArtifactSelection, ...] = Field(min_length=1)
    candidates: tuple[Entity, ...] = ()
    explanation: Text


class ProjectProposal(Record):
    proposal: EntityRef
    project: EntityRef
    domain: EntityRef
    design: EntityRef


class ArtifactInspection(Record):
    selection: ArtifactSelection
    receipt: ReviewReceipt | None = None
    approval_error: str | None = None


class ProjectInspection(Record):
    project: EntityRef
    manifest: ProjectManifest
    receipt: ReviewReceipt | None = None
    approval_error: str | None = None
    artifacts: tuple[ArtifactInspection, ...]
    stale_dependencies: tuple[Finding, ...]


def _identity(context_id, project_id):
    return 'authoring-project:' + hashlib.sha256(canonical([context_id, project_id]).encode()).hexdigest()


def _authorize(context):
    root = context.snapshot.context
    authorize(context.policy, context.request.subject_key, 'propose', root.ref)
    roles = set(context.participant.fields['roles']) & set(context.policy.subjects[context.request.subject_key].roles)
    if not roles & {'CONTENT_RESPONSIBLE', 'ADMINISTRATOR'}:
        raise ValueError('Project authoring requires content authority')


def _draft(context):
    if (context.snapshot.context.fields['mode'], context.snapshot.context.fields['status']) != ('PREPARATION', 'DRAFT'):
        raise ValueError('Project changes require a PREPARATION DRAFT context')


def _selected(store, context, project_id):
    """Find the direct catalogue entry, never a historical transitive reference."""
    identity = _identity(context.snapshot.context.id, project_id)
    found = []
    for model_ref in context.snapshot.context.fields['models']:
        model = context.snapshot.get(model_ref)
        if model.id == identity + ':model':
            found.extend(context.snapshot.get(r) for r in model.fields['definitions'] if r['id'] == identity)
    if len(found) != 1:
        raise ValueError('Project requires one current catalogue selection')
    return found[0]


def _manifest(resource, context):
    manifest = ProjectManifest.model_validate_json(resource.fields['contentOrLocator'])
    if (manifest.authoring_context != context.snapshot.context.id or
            resource.id != _identity(manifest.authoring_context, manifest.project_id)):
        raise ValueError('Project identity or owning context differs')
    return manifest


def _project(store, context, project_ref):
    _exact(project_ref, 'Resource')
    resource = store.read(project_ref, owner=context.snapshot.context.id)
    manifest = _manifest(resource, context)
    if _selected(store, context, manifest.project_id).ref != project_ref:
        raise StateConflict('Project revision is no longer selected')
    return resource, manifest


def _coverage(store, context, selection):
    resource = context.snapshot.get(selection.resource)
    receipt = review_receipt(store, context, resource)
    proposal = store.read(receipt.proposal, owner=context.snapshot.context.id)
    if not set(selection.definitions) <= {c.ref for c in proposal_candidates(store, proposal)}:
        raise ValueError('Artifact definitions were not reviewed with its exact resource')
    return receipt


def _persist(service, context, manifest, candidates, explanation):
    root = context.snapshot.context
    identity = _identity(root.id, manifest.project_id)
    version = uuid4().hex
    def make(kind, key, fields):
        return validate_entity(entity_data(make_entity(kind, key, fields, version=version,
            origin='GENERATED_PROPOSAL', responsible=context.request.subject_key)), context.contract)
    project = make('Resource', identity, {
        'title': 'Authoring project: ' + manifest.project_id,
        'topics': context.snapshot.get(next(a.resource for a in manifest.artifacts if a.kind == 'SYLLABUS')).fields['topics'],
        'contentOrLocator': manifest.model_dump_json(),
        'derivedFrom': [a.resource.model_dump() for a in manifest.artifacts],
        'usageConditions': 'Authoring selection only; release and delivery require separate review.'})
    entities = {**context.snapshot.entities, **{c.ref: c for c in candidates}, project.ref: project}
    # Follow exact definitions, rather than retaining the latest entity by id.
    pending = [project.ref, manifest.design, *(a.resource for a in manifest.artifacts),
               *(r for a in manifest.artifacts for r in a.definitions)]
    closure = {}
    while pending:
        reference = pending.pop()
        _exact(reference)
        if reference in closure:
            continue
        value = entities.get(reference)
        if value is None or context.contract.entity_types[value.type]['instanceLayer'] != 'domain_configuration':
            raise ValueError('Project closure requires authorized domain definitions')
        closure[reference] = value
        pending.extend(references(value.fields))
    if not {c.ref for c in candidates} <= closure.keys():
        raise ValueError('Candidate definitions must belong to the selected project closure')
    domain = make('DomainModel', identity + ':model', {
        'name': 'Authoring project: ' + manifest.project_id, 'scope': 'Exact reviewed authoring selection',
        'topics': [r.model_dump() for r in closure if r.type == 'Topic'],
        'outcomes': [r.model_dump() for r in closure if r.type == 'LearningOutcome'],
        'definitions': [r.model_dump() for r in closure]})
    updated = root.model_copy(update={'version': version, 'provenance': project.provenance,
        'fields': {**root.fields, 'learningDesign': manifest.design.model_dump(),
            'models': [*[m for m in root.fields['models'] if m['id'] != domain.id], domain.ref.model_dump()]}})
    all_candidates = (*candidates, project, domain, updated)
    proposal = create_proposal(context, (root.ref,), all_candidates, explanation)
    save_proposal(service.store, context, proposal, all_candidates)
    return ProjectProposal(proposal=proposal.ref, project=project.ref, domain=domain.ref, design=manifest.design)


def _initialize(store, context, command):
    root = context.snapshot.context
    identity = _identity(root.id, command.project_id)
    if any(m['id'] == identity + ':model' for m in root.fields['models']):
        raise StateConflict('Project already exists')
    context, artifacts, design = _curator_selection(store, context, command.syllabus)
    manifest = ProjectManifest(project_id=command.project_id, authoring_context=root.id,
        design=design, required_kinds=REQUIRED_KINDS, artifacts=artifacts)
    return context, manifest


def _curator_selection(store, context, syllabus_ref):
    root = context.snapshot.context
    approved = resolve_artifact(store, context, syllabus_ref)
    syllabus = store.read(approved.syllabus, owner=root.id)
    source = store.read(approved.artifact.source_snapshot, owner=root.id)
    saved = proposal_candidates(store, store.read(approved.proposal, owner=root.id))
    definitions = tuple(c.ref for c in saved if c.type not in {'DomainModel', 'ExecutionContext'}
                        and c.ref not in {syllabus.ref, source.ref})
    # Historical Curator definitions are accessible only through the proved owning proposal.
    context = replace(context, snapshot=replace(context.snapshot,
        entities={**context.snapshot.entities, **{c.ref: c for c in saved}}))
    artifacts = (
        ArtifactSelection(key='source', kind='SOURCE', resource=source.ref),
        ArtifactSelection(key='syllabus', kind='SYLLABUS', resource=syllabus.ref,
            depends_on=(source.ref,), definitions=definitions))
    return context, artifacts, approved.artifact.outline


def _revision_manifest(store, context, command):
    resource, previous = _project(store, context, command.project)
    review_receipt(store, context, resource)
    for selection in previous.artifacts:
        _coverage(store, context, selection)
    _exact(command.design, 'LearningDesign')
    candidates = tuple(validate_entity(entity_data(c), context.contract) for c in command.candidates)
    if len({c.ref for c in candidates}) != len(candidates):
        raise ValueError('Candidate references must be unique')
    for candidate in candidates:
        _exact(candidate.ref)
        if (context.contract.entity_types[candidate.type]['instanceLayer'] != 'domain_configuration' or
                candidate.type == 'DomainModel'):
            raise ValueError('Only artifact and design domain definitions may be supplied')
        try:
            existing = store.read(candidate.ref, owner=context.snapshot.context.id)
        except ValueError:
            existing = None
        if existing is not None and existing != candidate:
            raise ValueError('An active immutable definition cannot be overwritten')
    selected = {a.key: a for a in previous.artifacts}
    updated_keys = set()
    by_ref = {c.ref: c for c in candidates}
    for artifact in command.artifacts:
        if artifact.key in updated_keys:
            raise ValueError('Update slots must be unique')
        updated_keys.add(artifact.key)
        old = selected.get(artifact.key)
        if artifact.kind in {'SOURCE', 'SYLLABUS'}:
            if artifact.key != artifact.kind.lower() or old == artifact:
                raise ValueError('Curator updates require a changed canonical source/syllabus slot')
            selected[artifact.key] = artifact
            continue
        if old and (old.kind != artifact.kind or old.resource.id != artifact.resource.id or old.resource == artifact.resource):
            raise ValueError('Artifact updates require the same slot, kind and identity with a new version')
        if artifact.resource not in by_ref or not set(artifact.definitions) <= by_ref.keys():
            raise ValueError('Updated artifact and definitions must be supplied for joint review')
        if not artifact.depends_on or not set(artifact.depends_on) <= set(references(by_ref[artifact.resource].fields.get('derivedFrom', []))):
            raise ValueError('Artifact dependencies require explicit exact input lineage')
        selected[artifact.key] = artifact
    if updated_keys & {'source', 'syllabus'}:
        context, expected, _ = _curator_selection(store, context, selected['syllabus'].resource)
        if (selected['source'], selected['syllabus']) != expected:
            raise ValueError('Source/syllabus selections must match one exact approved Curator payload')
    for key in updated_keys - {'source', 'syllabus'}:
        if selected['syllabus'].resource not in selected[key].depends_on:
            raise ValueError('Authored artifacts must depend on the selected approved syllabus')
    manifest = previous.model_copy(update={'previous': resource.ref, 'design': command.design,
                                           'artifacts': tuple(selected.values())})
    manifest = ProjectManifest.model_validate(manifest.model_dump())
    if any(f.target in updated_keys for f in dependency_findings(manifest)):
        raise StateConflict('New artifacts use missing, stale or cyclic dependencies')
    return context, manifest, candidates


def propose_project(service, context_id, subject_key, command, request_id):
    payload = canonical({'operation': type(command).__name__, 'subject_key': subject_key,
                         'command': command.model_dump(mode='json')})
    with service.store.db:
        service.store.db.execute('BEGIN IMMEDIATE')
        context = service._context(context_id, subject_key)
        _authorize(context)
        LearningRequest(request_id=request_id, subject_key=subject_key,
            context_ref=command.base_context, text='Propose authoring project', intent='STATE')
        _exact(command.base_context, 'ExecutionContext')
        if command.base_context.id != context_id:
            raise ValueError('Base context belongs to another context')
        cached = service.store.request_result(request_id, context_id, payload)
        if cached is not None:
            return ProjectProposal.model_validate(cached)
        if command.base_context != context.snapshot.context.ref:
            raise StateConflict('Project request context is stale')
        _draft(context)
        service.store.db.execute('INSERT INTO requests VALUES (?,?,?,NULL)', (request_id, context_id, payload))
        if isinstance(command, ProjectInitialization):
            context, manifest = _initialize(service.store, context, command)
            result = _persist(service, context, manifest, (),
                'Initialize a project from the exact approved/applied Curator syllabus.')
        else:
            context, manifest, candidates = _revision_manifest(service.store, context, command)
            result = _persist(service, context, manifest, candidates, command.explanation)
        service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result


def inspect_project(service, context_id, subject_key, project_id):
    with service.store.db:
        service.store.db.execute('BEGIN')
        context = service._context(context_id, subject_key)
        _authorize(context)
        resource = _selected(service.store, context, project_id)
        manifest = _manifest(resource, context)
        receipt, error = None, None
        try:
            receipt = review_receipt(service.store, context, resource)
        except ValueError:
            error = 'Current approval/application or reviewer authority is invalid.'
        artifacts = []
        for selection in manifest.artifacts:
            try:
                artifacts.append(ArtifactInspection(selection=selection, receipt=_coverage(service.store, context, selection)))
            except ValueError:
                artifacts.append(ArtifactInspection(selection=selection,
                    approval_error='Exact artifact approval/application or definition coverage is invalid.'))
        return ProjectInspection(project=resource.ref, manifest=manifest, receipt=receipt,
            approval_error=error, artifacts=tuple(artifacts), stale_dependencies=dependency_findings(manifest))


def approved_project_syllabus(service, context_id, subject_key, project_ref):
    with service.store.db:
        service.store.db.execute('BEGIN')
        context = service._context(context_id, subject_key)
        _authorize(context)
        resource, manifest = _project(service.store, context, project_ref)
        review_receipt(service.store, context, resource)
        syllabuses = [a for a in manifest.artifacts if a.kind == 'SYLLABUS']
        if len(syllabuses) != 1 or any(f.target == syllabuses[0].key for f in dependency_findings(manifest)):
            raise ValueError('Project requires one fresh approved syllabus selection')
        _coverage(service.store, context, syllabuses[0])
        return resolve_artifact(service.store, context, syllabuses[0].resource)


def validate_project_application(store, context, candidates):
    """Recheck host project contracts under the application's SQLite write lock.

    Generic ALM proposals remain available. Reserved project identities must also
    satisfy this contract, including when submitted through the generic CLI.
    """
    projects = [c for c in candidates if c.type == 'Resource' and c.id.startswith('authoring-project:')]
    updated = next((c for c in candidates if c.type == 'ExecutionContext'), context.snapshot.context)
    old_models = {r['id']: r for r in context.snapshot.context.fields['models']
                  if r['id'].startswith('authoring-project:')}
    new_models = {r['id']: r for r in updated.fields['models']
                  if r['id'].startswith('authoring-project:')}
    for identity in old_models.keys() | new_models.keys():
        if old_models.get(identity) != new_models.get(identity):
            if not any(p.id + ':model' == identity for p in projects):
                raise ValueError('Project catalogue changes require a new reviewed project revision')
    for domain in (c for c in candidates if c.type == 'DomainModel' and c.id.startswith('authoring-project:')):
        if not any(p.id + ':model' == domain.id for p in projects):
            raise ValueError('Reserved project catalogues require their reviewed manifest')
    if not projects:
        return
    _authorize(context)
    _draft(context)
    for project in projects:
        pinned = ProjectManifest.model_validate_json(project.fields['contentOrLocator'])
        if pinned.authoring_context != context.snapshot.context.id:
            if store.read(project.ref, owner=context.snapshot.context.id) != project:
                raise ValueError('Foreign projects can only reuse an existing immutable definition')
            continue
        manifest = _manifest(project, context)
        if manifest.previous is None:
            syllabuses = [a for a in manifest.artifacts if a.kind == 'SYLLABUS']
            if len(syllabuses) != 1:
                raise ValueError('Initialization requires one selected Curator syllabus')
            _, expected = _initialize(store, context, ProjectInitialization(
                project_id=manifest.project_id, base_context=context.snapshot.context.ref,
                syllabus=syllabuses[0].resource))
        else:
            _, previous = _project(store, context, manifest.previous)
            prior = {a.key: a for a in previous.artifacts}
            updates = tuple(a for a in manifest.artifacts if prior.get(a.key) != a)
            supplied = tuple(c for c in candidates if c.type not in {'ExecutionContext', 'DomainModel'}
                             and c not in projects)
            _, expected, _ = _revision_manifest(store, context, ProjectRevision(project=manifest.previous,
                base_context=context.snapshot.context.ref, design=manifest.design,
                artifacts=updates, candidates=supplied, explanation='Revalidate reviewed project application'))
        if expected != manifest:
            raise ValueError('Reviewed project differs from its exact host-validated selection')
        domain = next((c for c in candidates if c.type == 'DomainModel' and c.id == project.id + ':model'), None)
        updated = next((c for c in candidates if c.type == 'ExecutionContext'), None)
        required = {project.ref, manifest.design, *(a.resource for a in manifest.artifacts),
                    *(r for a in manifest.artifacts for r in a.definitions)}
        if (domain is None or updated is None or
                not required <= set(references(domain.fields['definitions'])) or
                domain.ref.model_dump() not in updated.fields['models'] or
                updated.fields.get('learningDesign') != manifest.design.model_dump() or
                (updated.fields['mode'], updated.fields['status']) != ('PREPARATION', 'DRAFT')):
            raise ValueError('Project application requires its reviewed catalogue and draft context')
