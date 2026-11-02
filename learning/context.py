from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal

from learning.contracts import Entity, EntityRef, Finding, Record, Text
from learning.metamodel import Contract
from learning.policies import TrustedPolicy, authorize
from learning.store import LearningStore, StateConflict


class LearningRequest(Record):
    request_id: Text
    context_ref: EntityRef
    subject_key: Text
    text: Text
    references: tuple[EntityRef, ...] = ()
    topic_refs: tuple[EntityRef, ...] = ()
    activity_refs: tuple[EntityRef, ...] = ()
    occurrence_ref: EntityRef | None = None
    intent: Literal["EXPLAIN", "PRACTICE", "CURATE", "ASSESS", "SOCRATIC_GUIDANCE", "CLARIFICATION", "STATE"] = "EXPLAIN"
    problem_key: Text | None = None
    switch_from_socratic: bool = False


@dataclass(frozen=True)
class Snapshot:
    context: Entity
    base_version: str
    entities: dict[EntityRef, Entity]
    findings: tuple[Finding, ...] = ()
    rule_bindings: dict = field(default_factory=dict)

    def get(self, ref: EntityRef | dict) -> Entity:
        ref = EntityRef.model_validate(ref)
        try:
            return self.entities[ref]
        except KeyError:
            raise ValueError("Reference is outside the authorized snapshot") from None

    def of_type(self, kind: str) -> tuple[Entity, ...]:
        return tuple(e for e in self.entities.values() if e.type == kind)

    def active_domain(self) -> tuple[Entity, ...]:
        pending = [EntityRef.model_validate(ref) for ref in self.context.fields["models"]]
        found = {}
        while pending:
            ref = pending.pop()
            if ref in found or ref not in self.entities:
                continue
            entity = self.entities[ref]
            found[ref] = entity
            pending.extend(references(entity.fields))
        return tuple(found.values())


@dataclass(frozen=True)
class RunContext:
    snapshot: Snapshot
    policy: TrustedPolicy
    contract: Contract
    request: LearningRequest
    participant: Entity
    specializations: tuple[Entity, ...] = ()


def references(value) -> Iterable[EntityRef]:
    if isinstance(value, dict):
        if value.keys() == {"type", "id", "version"}:
            yield EntityRef.model_validate(value)
        else:
            for item in value.values():
                yield from references(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from references(item)


def load_context(store: LearningStore, request: LearningRequest, policy: TrustedPolicy,
                 contract: Contract) -> Snapshot:
    authorize(policy, request.subject_key, "read", request.context_ref)
    context = store.read_context(request.context_ref.id)
    if context.ref != request.context_ref:
        raise StateConflict("Requested context revision is stale")
    fields = context.fields
    if fields["metamodelVersion"] != contract.version or EntityRef.model_validate(fields["policies"]) != policy.policy_ref:
        raise ValueError("Context contract or trusted policy mismatch")
    if not fields["models"] and (fields["mode"], fields["status"]) != ("PREPARATION", "DRAFT"):
        raise ValueError("Context requires a domain model")
    participants = [store.read(EntityRef.model_validate(ref), owner=context.id) for ref in fields["participants"]]
    participant = next((p for p in participants if p.fields["subjectKey"] == request.subject_key), None)
    if participant is None or not set(participant.fields["roles"]) & set(policy.subjects[request.subject_key].roles):
        raise ValueError("Subject is not an authorized participant")
    learner_only = set(policy.subjects[request.subject_key].roles) <= {"LEARNER"}
    found, findings, visited = {}, [], set()
    pending = [context.ref]
    while pending:
        ref = pending.pop()
        if ref in visited:
            continue
        visited.add(ref)
        try:
            item = store.read(ref, owner=context.id)
        except ValueError:
            findings.append(Finding(code="R02", target=ref.id, reason="Required reference is unavailable."))
            continue
        if learner_only and "learner" in item.fields and EntityRef.model_validate(item.fields["learner"]) != participant.ref:
            continue
        found[ref] = item
        pending.extend(references(item.fields))
    selected = (*request.references, *request.topic_refs, *request.activity_refs)
    if request.occurrence_ref:
        selected += (request.occurrence_ref,)
    for ref in selected:
        if ref not in found:
            findings.append(Finding(code="R15", target=ref.id, reason="The requested reference is outside the authorized context."))
    from learning.rules import answer_key_match, all_true, all_completed
    handlers = {"answer_key_match": answer_key_match, "all_true": all_true, "all_completed": all_completed}
    bindings = {binding.rule: handlers[binding.handler] for binding in policy.rule_bindings
                if binding.rule.type == "RuleDefinition" and binding.rule in found}
    return Snapshot(context, context.version, found, tuple(findings), bindings)
