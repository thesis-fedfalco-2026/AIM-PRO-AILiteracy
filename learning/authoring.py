"""Read-only reference contracts for versioned authoring projects and releases.

These application manifests use existing Resource entities. Approval and writes
remain exclusively in the ALM proposal/decision/application lifecycle.
"""

from dataclasses import replace
from typing import Literal

from pydantic import Field, model_validator

from learning.context import references
from learning.contracts import Entity, EntityRef, Finding, Record, Text
from learning.decisions import approval_valid, proposal_candidates, review_payload_key
from learning.policies import authorize
from learning.store import canonical
from learning.validation import validate_snapshot


ArtifactKind = Literal['SOURCE', 'SYLLABUS', 'ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT']


def _exact(ref, kind=None):
    if ref.version.lower() == 'latest' or kind is not None and ref.type != kind:
        raise ValueError('Authoring manifests require exact references of the declared type')


class ArtifactSelection(Record):
    key: Text
    kind: ArtifactKind
    resource: EntityRef
    depends_on: tuple[EntityRef, ...] = ()
    definitions: tuple[EntityRef, ...] = ()

    @model_validator(mode='after')
    def exact_references(self):
        for ref in (self.resource, *self.depends_on):
            _exact(ref, 'Resource')
        for ref in self.definitions:
            _exact(ref)
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError('Artifact dependencies must be unique')
        return self


class ProjectManifest(Record):
    format: Literal['authoring-project'] = 'authoring-project'
    format_version: Literal[1] = 1
    project_id: Text
    authoring_context: Text
    previous: EntityRef | None = None
    design: EntityRef
    required_kinds: tuple[ArtifactKind, ...] = Field(min_length=1)
    artifacts: tuple[ArtifactSelection, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_selection(self):
        _exact(self.design, 'LearningDesign')
        if self.previous:
            _exact(self.previous, 'Resource')
        keys = [a.key for a in self.artifacts]
        identities = [(a.resource.type, a.resource.id) for a in self.artifacts]
        if len(set(keys)) != len(keys) or len(set(identities)) != len(identities):
            raise ValueError('Select one current version per artifact identity and key')
        if len(set(self.required_kinds)) != len(self.required_kinds):
            raise ValueError('Required artifact kinds must be unique')
        return self


class ReleaseManifest(Record):
    format: Literal['authoring-release'] = 'authoring-release'
    format_version: Literal[1] = 1
    authoring_context: Text
    project: EntityRef
    domain: EntityRef
    design: EntityRef
    artifacts: tuple[EntityRef, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def exact_references(self):
        for ref in (self.project, *self.artifacts):
            _exact(ref, 'Resource')
        _exact(self.domain, 'DomainModel')
        _exact(self.design, 'LearningDesign')
        return self


class ReviewReceipt(Record):
    proposal: EntityRef
    decision: EntityRef
    change: EntityRef


def review_receipt(store, context, resource):
    """Prove approval/application in its owning authoring context, without writes."""
    root = context.snapshot.context
    authorize(context.policy, context.request.subject_key, 'propose', root.ref)
    _exact(resource.ref, 'Resource')
    if store.read(resource.ref, owner=root.id) != resource:
        raise ValueError('Authoring resource payload differs from its stored version')
    for proposal in store.owned(root.id, 'ChangeProposal'):
        if proposal.fields['status'] != 'APPLIED' or resource.ref.model_dump() not in proposal.fields['candidateDefinitions']:
            continue
        saved = proposal_candidates(store, proposal)
        if not any(c == resource for c in saved):
            continue
        decision = store.read(EntityRef.model_validate(proposal.fields['decision']), owner=root.id)
        reviewed = store.read(EntityRef.model_validate(decision.fields['target']), owner=root.id)
        entities = {**context.snapshot.entities, **{c.ref: c for c in saved},
                    proposal.ref: proposal, decision.ref: decision, reviewed.ref: reviewed}
        if not approval_valid(proposal, replace(context.snapshot, entities=entities), context.policy):
            continue
        for change in store.owned(root.id, 'StateChange'):
            cause = EntityRef.model_validate(change.fields['cause'])
            if cause.id != proposal.id or change.fields['authorizationBasis'] != canonical(decision.ref.model_dump()):
                continue
            applied = store.read(cause, owner=root.id)
            if (applied.fields.get('status') == 'APPROVED' and
                    change.fields['baseVersion'] == proposal.fields['baseContextVersion'] and
                    review_payload_key(applied, saved) == proposal.fields['reviewPayloadKey']):
                return ReviewReceipt(proposal=proposal.ref, decision=decision.ref, change=change.ref)
    raise ValueError('An exact approved and applied authoring proposal is required')


def dependency_findings(project):
    """Derive freshness for this selection; historical approvals are not revoked."""
    selected = {a.resource: a for a in project.artifacts}
    invalid = set()
    edges = {a.resource: set(a.depends_on) for a in project.artifacts}
    for ref, dependencies in edges.items():
        if not dependencies <= selected.keys():
            invalid.add(ref)
    # Visit each edge once; even a dense acyclic graph must remain inexpensive.
    states, path = {}, []
    def visit(ref):
        if states.get(ref) == 1:
            invalid.update(path[path.index(ref):])
            return
        if states.get(ref) == 2:
            return
        states[ref] = 1
        path.append(ref)
        for dep in edges[ref]:
            if dep in selected:
                visit(dep)
        path.pop()
        states[ref] = 2
    for ref in selected:
        visit(ref)
    while True:
        impacted = invalid | {ref for ref, deps in edges.items() if deps & invalid}
        if impacted == invalid:
            break
        invalid = impacted
    return tuple(Finding(code='AUTHORING_STALE_DEPENDENCY', target=a.key,
        reason='A selected dependency is missing, superseded, cyclic or itself stale.')
        for a in project.artifacts if a.resource in invalid)


def prepare_release(store, context, project_resource, domain_ref):
    """Build a release manifest for review, not an approval or runtime activation."""
    root = context.snapshot.context
    if (root.fields['mode'], root.fields['status']) != ('PREPARATION', 'DRAFT'):
        raise ValueError('Release preparation requires a draft authoring context')
    project = ProjectManifest.model_validate_json(project_resource.fields['contentOrLocator'])
    if project.authoring_context != root.id or root.fields.get('learningDesign') != project.design.model_dump():
        raise ValueError('Project must select the current authoring design in its owning context')
    if project_resource.ref not in {e.ref for e in context.snapshot.active_domain()}:
        raise ValueError('Project is outside the current authoring model')
    if dependency_findings(project) or not set(project.required_kinds) <= {a.kind for a in project.artifacts}:
        raise ValueError('Project has missing or stale authoring artifacts')
    domain = context.snapshot.get(domain_ref)
    _exact(domain.ref, 'DomainModel')
    definitions = {EntityRef.model_validate(ref) for ref in domain.fields['definitions']}
    expected = {project_resource.ref, project.design,
                *(a.resource for a in project.artifacts),
                *(ref for a in project.artifacts for ref in a.definitions)}
    if not expected <= definitions or validate_snapshot(context.snapshot):
        raise ValueError('Release domain does not contain consistent selected definitions')
    receipt = review_receipt(store, context, project_resource)
    reviewed_project = store.read(receipt.proposal, owner=root.id)
    if domain.ref.model_dump() not in reviewed_project.fields['candidateDefinitions']:
        raise ValueError('Release domain was not reviewed with this project revision')
    for artifact in project.artifacts:
        review_receipt(store, context, context.snapshot.get(artifact.resource))
    return ReleaseManifest(authoring_context=root.id, project=project_resource.ref,
        domain=domain.ref, design=project.design, artifacts=tuple(a.resource for a in project.artifacts))


def released_entities(store, context, release_resource):
    """Read an approved frozen domain for explicit import into another context.

    The caller must hold a read transaction. Runtime binding approval, policy and
    activation remain separate operations in that destination context.
    """
    review_receipt(store, context, release_resource)
    release = ReleaseManifest.model_validate_json(release_resource.fields['contentOrLocator'])
    if release.authoring_context != context.snapshot.context.id:
        raise ValueError('Release belongs to another authoring context')
    project_resource = store.read(release.project, owner=release.authoring_context)
    receipt = review_receipt(store, context, project_resource)
    reviewed_project = store.read(receipt.proposal, owner=release.authoring_context)
    if release.domain.model_dump() not in reviewed_project.fields['candidateDefinitions']:
        raise ValueError('Release domain was not reviewed with this project revision')
    project = ProjectManifest.model_validate_json(project_resource.fields['contentOrLocator'])
    if (project.authoring_context != release.authoring_context or project.design != release.design or
            tuple(a.resource for a in project.artifacts) != release.artifacts or dependency_findings(project)):
        raise ValueError('Release pins do not match its reviewed project')
    for ref in release.artifacts:
        review_receipt(store, context, store.read(ref, owner=release.authoring_context))
    found, pending = {}, [release.domain]
    while pending:
        ref = pending.pop()
        if ref in found:
            continue
        entity = store.read(ref, owner=release.authoring_context)
        if context.contract.entity_types[entity.type]['instanceLayer'] != 'domain_configuration':
            raise ValueError('A release cannot import authoring execution state')
        found[ref] = entity
        pending.extend(references(entity.fields))
    if not {release.project, release.design, *release.artifacts} <= found.keys():
        raise ValueError('Release domain omits its exact project, design or artifacts')
    return release, tuple(found[ref] for ref in sorted(found, key=lambda r: (r.type, r.id, r.version)))
