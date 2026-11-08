from __future__ import annotations

from dataclasses import replace
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
from uuid import uuid4

from learning.contracts import Entity, EntityRef, entity_data, make_entity
from learning.context import RunContext, Snapshot, references
from learning.metamodel import validate_entity
from learning.policies import TrustedPolicy, authorize
from learning.store import LearningStore, StateConflict, canonical
from learning.validation import validate_snapshot, check_readiness


def _payload(entity: Entity) -> dict:
    excluded = {"reviewPayloadKey"}
    if entity.type == "ChangeProposal":
        excluded |= {"status", "decision"}
    elif entity.type == "ResourceBinding":
        excluded.add("approvalDecision")
    elif entity.type == "Evaluation":
        excluded.add("humanDecision")
    return {"type": entity.type, "id": entity.id, "provenance": entity.provenance.model_dump(exclude_none=True),
            "fields": {key: value for key, value in entity.fields.items() if key not in excluded}}


def review_payload_key(target: Entity, candidates: tuple[Entity, ...] = ()) -> str:
    payload = {"target": _payload(target), "candidates": [
        {**_payload(candidate), "version": candidate.version}
        for candidate in sorted(candidates, key=lambda item: (item.type, item.id, item.version))]}
    return hashlib.sha256(canonical(payload).encode()).hexdigest()


def reviewed_candidate(entity: Entity) -> Entity:
    if entity.type in {"ResourceBinding", "Evaluation"}:
        return entity.model_copy(update={"fields": {**entity.fields, "reviewPayloadKey": review_payload_key(entity)}})
    return entity


def _reviewer_allowed(participant: Entity, policy: TrustedPolicy, context_ref: EntityRef,
                      target: Entity, candidates: tuple[Entity, ...] = ()) -> None:
    subject = participant.fields["subjectKey"]
    authorize(policy, subject, "decide", context_ref)
    roles = set(participant.fields["roles"]) & set(policy.subjects[subject].roles)
    if "ADMINISTRATOR" in roles:
        return
    kinds = {target.type, *(candidate.type for candidate in candidates)}
    if kinds & {"Participant", "PolicySet"}:
        raise ValueError("Administrative authority is required")
    if "Evaluation" in kinds and "ASSESSOR" not in roles:
        raise ValueError("Assessment authority is required")
    if kinds - {"Evaluation", "ChangeProposal"} and "CONTENT_RESPONSIBLE" not in roles:
        raise ValueError("Content authority is required")


def approval_valid(entity: Entity, snapshot: Snapshot, policy: TrustedPolicy) -> bool:
    link = {"ResourceBinding": "approvalDecision", "Evaluation": "humanDecision", "ChangeProposal": "decision"}.get(entity.type)
    if not link or not entity.fields.get(link):
        return False
    try:
        decision = snapshot.get(entity.fields[link])
        if decision.type != "HumanDecision" or decision.fields["decision"] != "APPROVE":
            return False
        if decision.fields["context"]["id"] != snapshot.context.id:
            return False
        target = snapshot.get(decision.fields["target"])
        candidates = tuple(snapshot.get(ref) for ref in target.fields.get("candidateDefinitions", []))
        key = review_payload_key(target, candidates)
        expected = {key, *(review_payload_key(candidate) for candidate in candidates
                           if candidate.type in {"ResourceBinding", "Evaluation"})}
        if decision.fields["reviewedPayloadKey"] != key or set(decision.fields["coveredPayloadKeys"]) != expected:
            return False
        own_candidates = candidates if entity.type == "ChangeProposal" else ()
        own_key = review_payload_key(entity, own_candidates)
        if entity.fields["reviewPayloadKey"] != own_key or own_key not in expected:
            return False
        if entity.id != target.id and not any(c.id == entity.id and c.type == entity.type
                                              and review_payload_key(c) == own_key for c in candidates):
            return False
        historical = snapshot.get(decision.fields["decider"])
        current = next((snapshot.get(ref) for ref in snapshot.context.fields["participants"]
                        if snapshot.get(ref).fields["subjectKey"] == historical.fields["subjectKey"]), None)
        if current is None:
            return False
        _reviewer_allowed(current, policy, snapshot.context.ref, target, candidates)
        return True
    except (ValueError, KeyError, TypeError):
        return False


def _validate_candidates(context: RunContext, candidates: tuple[Entity, ...]) -> Snapshot:
    if not candidates or len({c.ref for c in candidates}) != len(candidates):
        raise ValueError("Proposal requires unique structured candidates")
    allowed_state = {"ExecutionContext", "Participant", "ResourceBinding", "Evaluation"}
    entities = dict(context.snapshot.entities)
    for candidate in candidates:
        validate_entity(entity_data(candidate), context.contract)
        if context.contract.entity_types[candidate.type]["instanceLayer"] == "execution_state" and candidate.type not in allowed_state:
            raise ValueError("Candidate cannot assign authoritative learning state or authority records")
        if candidate.type == "ExecutionContext" and candidate.id != context.snapshot.context.id:
            raise ValueError("Proposal cannot change another context")
        if "context" in candidate.fields and candidate.fields["context"]["id"] != context.snapshot.context.id:
            raise ValueError("Candidate belongs to another context")
        if candidate.ref in entities and entity_data(entities[candidate.ref]) != entity_data(candidate):
            raise ValueError("A changed candidate requires a new version")
        entities[candidate.ref] = candidate
    for candidate in candidates:
        if any(ref not in entities for ref in references(candidate.fields)):
            raise ValueError("Candidate contains an unresolved or unauthorized reference")
    root = next((c for c in candidates if c.type == "ExecutionContext"), context.snapshot.context)
    snapshot = replace(context.snapshot, context=root, entities=entities, findings=())
    from learning.assessment import validate_evaluation
    if any(validate_evaluation(candidate, snapshot) for candidate in candidates if candidate.type == "Evaluation"):
        raise ValueError("Candidate evaluation lacks admissible evidence or criteria")
    if any(f.severity == "BLOCKING" for f in validate_snapshot(snapshot)):
        raise ValueError("Candidate violates ALM invariants")
    if root.fields["metamodelVersion"] != context.contract.version:
        raise ValueError("Candidate cannot change the fixed contract")
    if not root.fields["models"] and (root.fields["mode"], root.fields["status"]) != ("PREPARATION", "DRAFT"):
        raise ValueError("Active learning requires a model")
    if root.fields.get("learningDesign") and root.fields["status"] == "ACTIVE":
        if any(f.severity == "BLOCKING" for f in check_readiness(snapshot, root.fields["learningDesign"], "advance",
                learner_ref=context.participant.ref, policy=context.policy, subject_key=context.request.subject_key)):
            raise ValueError("Learning design is not ready")
    return snapshot


def create_proposal(context: RunContext, target_refs: tuple[EntityRef, ...], candidates: tuple[Entity, ...],
                    explanation: str) -> Entity:
    authorize(context.policy, context.request.subject_key, "propose", context.snapshot.context.ref)
    if not target_refs:
        raise ValueError("Proposal requires a target")
    for ref in target_refs:
        context.snapshot.get(ref)
    candidates = tuple(reviewed_candidate(validate_entity(entity_data(c), context.contract)) for c in candidates)
    _validate_candidates(context, candidates)
    proposal = make_entity("ChangeProposal", f"proposal-{uuid4().hex}", {
        "context": context.snapshot.context.ref.model_dump(), "targets": [ref.model_dump() for ref in target_refs],
        "proposedChange": explanation, "justification": explanation, "findings": [],
        "status": "AWAITING_DECISION", "baseContextVersion": context.snapshot.base_version,
        "reviewPayloadKey": "pending", "candidateDefinitions": [c.ref.model_dump() for c in candidates]},
        origin="GENERATED_PROPOSAL", responsible=context.request.subject_key)
    return proposal.model_copy(update={"fields": {**proposal.fields, "reviewPayloadKey": review_payload_key(proposal, candidates)}})


def save_proposal(store: LearningStore, context: RunContext, proposal: Entity, candidates: tuple[Entity, ...]) -> None:
    authorize(context.policy, context.request.subject_key, "propose", context.snapshot.context.ref)
    candidates = tuple(reviewed_candidate(validate_entity(entity_data(c), context.contract)) for c in candidates)
    _validate_candidates(context, candidates)
    if proposal.fields["reviewPayloadKey"] != review_payload_key(proposal, candidates):
        raise ValueError("Proposal content does not match reviewed payload")
    with (nullcontext() if store.db.in_transaction else store.db):
        store._put(proposal, context.snapshot.context.id)
        for candidate in candidates:
            store._put(candidate, context.snapshot.context.id, canonical(proposal.ref.model_dump()))


def proposal_candidates(store: LearningStore, proposal: Entity) -> tuple[Entity, ...]:
    visited = set()
    current = proposal
    while current.ref not in visited:
        visited.add(current.ref)
        candidates = store.candidates(current.ref)
        if candidates:
            if {c.ref for c in candidates} != {EntityRef.model_validate(ref) for ref in proposal.fields["candidateDefinitions"]}:
                raise ValueError("Proposal candidate set has changed")
            return candidates
        if not current.fields.get("decision"):
            break
        decision = store.read(EntityRef.model_validate(current.fields["decision"]), owner=proposal.fields["context"]["id"])
        current = store.read(EntityRef.model_validate(decision.fields["target"]), owner=proposal.fields["context"]["id"])
    raise ValueError("Proposal candidates are unavailable")


def _latest(store: LearningStore, target: Entity, owner: str) -> Entity:
    return next((e for e in store.owned(owner, target.type) if e.id == target.id), target)


def record_decision(store: LearningStore, context: RunContext, target: EntityRef, decision: str, reason: str) -> Entity:
    reviewed = store.read(target, owner=context.snapshot.context.id)
    if reviewed.type not in {"ChangeProposal", "ResourceBinding", "Evaluation"} or decision not in {"APPROVE", "REJECT", "REQUEST_REVISION"}:
        raise ValueError("Invalid decision target or kind")
    candidates = proposal_candidates(store, reviewed) if reviewed.type == "ChangeProposal" else ()
    _reviewer_allowed(context.participant, context.policy, context.snapshot.context.ref, reviewed, candidates)
    key = review_payload_key(reviewed, candidates)
    current = _latest(store, reviewed, context.snapshot.context.id)
    if key != reviewed.fields["reviewPayloadKey"] or key != review_payload_key(current, candidates):
        raise ValueError("Reviewed content changed")
    if reviewed.type == "ChangeProposal":
        _validate_candidates(context, candidates)
    keys = sorted({key, *(review_payload_key(c) for c in candidates if c.type in {"ResourceBinding", "Evaluation"})})
    result = make_entity("HumanDecision", f"decision-{uuid4().hex}", {
        "context": context.snapshot.context.ref.model_dump(), "decider": context.participant.ref.model_dump(),
        "target": target.model_dump(), "decision": decision, "reason": reason,
        "decidedAt": datetime.now(timezone.utc).isoformat(), "reviewedPayloadKey": key, "coveredPayloadKeys": keys},
        origin="HUMAN_DECISION", responsible=context.request.subject_key)
    link = {"ChangeProposal": "decision", "ResourceBinding": "approvalDecision", "Evaluation": "humanDecision"}[reviewed.type]
    fields = {**current.fields, link: result.ref.model_dump()}
    if reviewed.type == "ChangeProposal":
        fields["status"] = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_REVISION": "DRAFT"}[decision]
    revision = current.model_copy(update={"version": uuid4().hex, "fields": fields})
    with store.db:
        store._put(result, context.snapshot.context.id)
        store._put(revision, context.snapshot.context.id)
    return result


def apply_proposal(store: LearningStore, context: RunContext, proposal: EntityRef, *, operation_id: str) -> Entity:
    authorize(context.policy, context.request.subject_key, "apply", context.snapshot.context.ref)
    original = store.read(proposal, owner=context.snapshot.context.id)
    if original.type != "ChangeProposal":
        raise ValueError("Application requires a structured change proposal")
    current = _latest(store, original, context.snapshot.context.id)
    candidates = proposal_candidates(store, current)
    if review_payload_key(original, candidates) != review_payload_key(current, candidates):
        raise ValueError("Proposal content changed since review")
    previous = store.operation_result(operation_id, context.snapshot.context.id)
    if previous:
        if previous.fields["cause"]["id"] != current.id:
            raise StateConflict("Operation identity refers to another proposal")
        return previous
    if current.fields["status"] != "APPROVED":
        raise ValueError("Proposal is not approved")
    decision = store.read(EntityRef.model_validate(current.fields["decision"]), owner=context.snapshot.context.id)
    reviewed = store.read(EntityRef.model_validate(decision.fields["target"]), owner=context.snapshot.context.id)
    entities = {**context.snapshot.entities, current.ref: current, decision.ref: decision, reviewed.ref: reviewed,
                **{c.ref: c for c in candidates}}
    snapshot = replace(context.snapshot, entities=entities)
    if not approval_valid(current, snapshot, context.policy):
        raise ValueError("Approval does not cover this payload")
    root = store.read_context(context.snapshot.context.id)
    if root.version != current.fields["baseContextVersion"]:
        stale = current.model_copy(update={"version": uuid4().hex, "fields": {**current.fields, "status": "STALE"}})
        store.record_event(operation_id, stale)
        raise StateConflict("Proposal base is stale")
    _validate_candidates(context, candidates)
    applied = []
    for candidate in candidates:
        link = {"ResourceBinding": "approvalDecision", "Evaluation": "humanDecision"}.get(candidate.type)
        if link:
            candidate = candidate.model_copy(update={"fields": {**candidate.fields, link: decision.ref.model_dump()}})
        applied.append(candidate)
    updated = next((c for c in applied if c.type == "ExecutionContext"), None)
    if updated is None:
        updated = root.model_copy(update={"version": uuid4().hex})
        applied.append(updated)
    if updated.version == root.version:
        raise ValueError("Context update requires a new version")
    from learning.assessment import derive_learning_state
    assessment_snapshot = replace(snapshot, entities={**snapshot.entities, **{e.ref: e for e in applied}})
    states = []
    for evaluation in applied:
        if evaluation.type != "Evaluation":
            continue
        specification = assessment_snapshot.get(evaluation.fields["specification"])
        for outcome in specification.fields["outcomes"]:
            state = derive_learning_state(replace(context, snapshot=assessment_snapshot), evaluation,
                context.snapshot.rule_bindings, outcome_ref=EntityRef.model_validate(outcome))
            states.append(state)
    if states:
        replaced = {(canonical(s.fields["learner"]), canonical(s.fields["outcome"])) for s in states}
        retained = [ref for ref in updated.fields["learningStates"] if
                    (canonical(snapshot.get(ref).fields["learner"]), canonical(snapshot.get(ref).fields["outcome"])) not in replaced]
        revised = updated.model_copy(update={"fields": {**updated.fields,
            "learningStates": [*retained, *(state.ref.model_dump() for state in states)]}})
        applied = [revised if entity.ref == updated.ref else entity for entity in applied]
        applied.extend(states)
    status = current.model_copy(update={"version": uuid4().hex, "fields": {**current.fields, "status": "APPLIED"}})
    change = make_entity("StateChange", f"change-{uuid4().hex}", {
        "context": root.ref.model_dump(), "baseVersion": root.version, "newVersion": updated.version,
        "cause": current.ref.model_dump(), "authorizationBasis": canonical(decision.ref.model_dump()),
        "change": current.fields["proposedChange"], "recordedAt": datetime.now(timezone.utc).isoformat()},
        origin="HUMAN_DECISION", responsible=context.request.subject_key)
    def project_precondition():
        from learning.context import load_context
        from learning.projects import validate_project_application
        from learning.releases import validate_release_application
        if _latest(store, current, root.id) != current:
            raise StateConflict('Proposal decision changed before application')
        fresh = replace(context, snapshot=load_context(store, context.request, context.policy, context.contract))
        validate_project_application(store, fresh, candidates)
        validate_release_application(store, fresh, current, candidates)
    return store.commit_change(change, (*applied, status), expected_version=root.version,
                               operation_id=operation_id, precondition=project_precondition)
