from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from learning.contracts import Entity, EntityRef, Finding, entity_data, make_entity
from learning.context import RunContext, Snapshot
from learning.metamodel import load_contract, validate_entity
from learning.policies import authorize
from learning.rules import RuleBindings, evaluate_rule
from learning.store import LearningStore, StateConflict, canonical
from learning.validation import check_readiness


def record_attempt(store: LearningStore, context: RunContext, activity: EntityRef | dict,
                   content: str, *, request_id: str) -> Entity:
    root, learner = context.snapshot.context, context.participant
    authorize(context.policy, context.request.subject_key, "submit", root.ref)
    if "LEARNER" not in set(learner.fields["roles"]) & set(context.policy.subjects[context.request.subject_key].roles):
        raise ValueError("Only the learner can submit their attempt")
    activity = context.snapshot.get(activity)
    if activity.type != "ActivityDefinition" or not isinstance(content, str) or not content.strip():
        raise ValueError("An activity and a real response are required")
    operation_id = f"attempt:{root.id}:{request_id}"
    previous = store.operation_result(operation_id, root.id)
    if previous:
        evidence = store.read(EntityRef.model_validate(previous.fields["cause"]), owner=root.id)
        if (evidence.fields["activity"] != activity.ref.model_dump()
                or evidence.fields["learner"] != learner.ref.model_dump()
                or evidence.fields["contentOrLocator"] != content):
            raise StateConflict("Attempt identity has different content")
        return evidence
    if activity.ref not in {entity.ref for entity in context.snapshot.active_domain()}:
        raise ValueError("Activity is not in the active model")
    if root.fields["mode"] != "LEARNING" or root.fields["status"] != "ACTIVE":
        raise ValueError("Attempts require active learning")
    if any(f.severity == "BLOCKING" for f in check_readiness(context.snapshot, activity.ref, "interact",
            learner_ref=learner.ref, policy=context.policy, subject_key=context.request.subject_key)):
        raise ValueError("Activity is not ready")
    kinds = activity.fields["expectedEvidence"]
    if len(kinds) != 1 or not activity.fields["outcomes"]:
        raise ValueError("A unique evidence kind and outcomes must be defined first")
    if activity.fields.get("assessmentSpec"):
        spec = context.snapshot.get(activity.fields["assessmentSpec"])
        if kinds[0] not in spec.fields["allowedEvidence"] or activity.ref.model_dump() not in spec.fields["activities"]:
            raise ValueError("Activity evidence is not allowed by the assessment")
    key = uuid4().hex
    occurrence_ref = EntityRef(type="ActivityOccurrence", id=f"occurrence-{key}", version="1")
    common = {"context": root.ref.model_dump(), "learner": learner.ref.model_dump(), "activity": activity.ref.model_dump()}
    evidence = make_entity("LearningEvidence", f"evidence-{key}", {**common,
        "occurrence": occurrence_ref.model_dump(), "outcomes": activity.fields["outcomes"], "kind": kinds[0],
        "contentOrLocator": content, "observedAt": datetime.now(timezone.utc).isoformat()},
        origin="OBSERVED_EVENT", responsible=context.request.subject_key)
    occurrence = make_entity("ActivityOccurrence", occurrence_ref.id, {**common,
        "attemptKey": request_id, "status": "IN_PROGRESS", "evidence": [evidence.ref.model_dump()]},
        origin="OBSERVED_EVENT", responsible=context.request.subject_key)
    updated = root.model_copy(update={"version": uuid4().hex, "fields": {**root.fields,
        "activityOccurrences": [*root.fields["activityOccurrences"], occurrence.ref.model_dump()]}})
    change = make_entity("StateChange", f"change-{key}", {
        "context": root.ref.model_dump(), "baseVersion": root.version, "newVersion": updated.version,
        "cause": evidence.ref.model_dump(), "authorizationBasis": canonical(context.policy.policy_ref.model_dump()),
        "change": "Recorded the observed attempt without inferring acquisition or verification.",
        "recordedAt": datetime.now(timezone.utc).isoformat()}, origin="OBSERVED_EVENT", responsible=context.request.subject_key)
    store.commit_change(change, (occurrence, evidence, updated), expected_version=root.version, operation_id=operation_id)
    return evidence


def validate_evaluation(evaluation: Entity, snapshot: Snapshot) -> tuple[Finding, ...]:
    try:
        validate_entity(entity_data(evaluation), load_contract())
        if evaluation.type != "Evaluation" or evaluation.fields["context"]["id"] != snapshot.context.id:
            raise ValueError("Evaluation context mismatch")
        specification = snapshot.get(evaluation.fields["specification"])
        evidence = tuple(snapshot.get(ref) for ref in evaluation.fields["evidence"])
        learners = set()
        covered = set()
        for item in evidence:
            occurrence = snapshot.get(item.fields["occurrence"])
            activity = snapshot.get(item.fields["activity"])
            if activity.fields.get("assessmentSpec") != specification.ref.model_dump():
                raise ValueError("Assessment must use the specification fixed for the activity")
            if item.provenance.origin != "OBSERVED_EVENT" or occurrence.provenance.origin != "OBSERVED_EVENT":
                raise ValueError("Assessment requires observed evidence")
            if any(item.fields[key] != occurrence.fields[key] for key in ("context", "learner", "activity")):
                raise ValueError("Evidence does not match its occurrence")
            if item.fields["context"]["id"] != snapshot.context.id or item.ref.model_dump() not in occurrence.fields["evidence"]:
                raise ValueError("Evidence is not part of this attempt")
            learners.add(EntityRef.model_validate(item.fields["learner"]))
            if item.fields["kind"] not in specification.fields["allowedEvidence"] or item.fields["activity"] not in specification.fields["activities"]:
                raise ValueError("Evidence is not permitted by this specification")
            covered.update(EntityRef.model_validate(ref) for ref in item.fields["outcomes"])
        if len(learners) != 1 or not {EntityRef.model_validate(ref) for ref in specification.fields["outcomes"]} <= covered:
            raise ValueError("Assessment has incomplete or mixed learner evidence")
        judgments = evaluation.fields.get("criterionJudgments", [])
        if specification.fields.get("rubric"):
            rubric = snapshot.get(specification.fields["rubric"])
            criteria = {criterion["key"]: criterion for criterion in rubric.fields["criteria"]}
            if len(judgments) != len(criteria) or {j["criterionKey"] for j in judgments} != set(criteria):
                raise ValueError("Every rubric criterion needs a judgment or an explicit unknown")
            for judgment in judgments:
                criterion = criteria[judgment["criterionKey"]]
                if judgment.get("levelKey") and judgment["levelKey"] not in {level["key"] for level in criterion["levels"]}:
                    raise ValueError("Judgment uses an unknown rubric level")
                if not {EntityRef.model_validate(ref) for ref in judgment["evidenceRefs"]} <= {e.ref for e in evidence}:
                    raise ValueError("Judgment refers to unassessed evidence")
        elif judgments:
            raise ValueError("Criterion judgments require a fixed rubric")
    except (ValueError, KeyError, TypeError):
        return (Finding(code="R11", target=evaluation.id, reason="The evaluation lacks consistent and admissible evidence or criteria."),)
    return ()


def derive_learning_state(context: RunContext, evaluation: Entity, bindings: RuleBindings,
                          *, outcome_ref: EntityRef | None = None) -> Entity:
    from learning.decisions import approval_valid

    if validate_evaluation(evaluation, context.snapshot):
        raise ValueError("Invalid assessment cannot determine learning state")
    spec = context.snapshot.get(evaluation.fields["specification"])
    if outcome_ref is None:
        if len(spec.fields["outcomes"]) != 1:
            raise ValueError("Choose one assessed outcome")
        outcome_ref = EntityRef.model_validate(spec.fields["outcomes"][0])
    if outcome_ref.model_dump() not in spec.fields["outcomes"]:
        raise ValueError("Outcome is outside the assessment")
    outcome = context.snapshot.get(outcome_ref)
    evidence = [context.snapshot.get(ref) for ref in evaluation.fields["evidence"]]
    inputs = {"answers": [e.fields["contentOrLocator"] for e in evidence], "answer_key": spec.fields.get("answerKey")}
    def satisfied(ref):
        return bool(ref) and evaluate_rule(EntityRef.model_validate(ref), context.snapshot, inputs, bindings) == "SATISFIED"
    acquired = satisfied(outcome.fields.get("achievementRule")) and satisfied(spec.fields.get("decisionRule"))
    formal = evaluation.fields["mode"] == "FORMAL"
    verified = acquired and formal and satisfied(outcome.fields.get("verificationRule")) and approval_valid(evaluation, context.snapshot, context.policy)
    return make_entity("LearningState", f"state-{uuid4().hex}", {
        "context": context.snapshot.context.ref.model_dump(), "learner": evidence[0].fields["learner"],
        "outcome": outcome.ref.model_dump(), "progress": "ACQUIRED" if acquired else "IN_PROGRESS",
        "verification": "VERIFIED" if verified else "PENDING_CONFIRMATION" if acquired and formal else "UNVERIFIED",
        "basis": [evaluation.ref.model_dump()]}, origin="OBSERVED_EVENT", responsible=context.request.subject_key)


def derive_activity_status(occurrence: Entity, snapshot: Snapshot, bindings: RuleBindings,
                           *, learner_ref: EntityRef | None = None) -> str:
    rule = occurrence.fields.get("completionRule")
    if not rule:
        return occurrence.fields.get("status", "IN_PROGRESS")
    if occurrence.type == "ProcessNode":
        if learner_ref is None:
            raise ValueError("Process completion requires an explicit learner")
        if occurrence.fields["kind"] == "PHASE":
            inputs = {EntityRef.model_validate(ref).id: derive_activity_status(snapshot.get(ref), snapshot, bindings, learner_ref=learner_ref)
                      for ref in occurrence.fields["children"]}
        else:
            items = [snapshot.get(ref) for ref in snapshot.context.fields["activityOccurrences"]
                     if EntityRef.model_validate(ref) in snapshot.entities]
            inputs = {}
            for ref in occurrence.fields["activities"]:
                matches = [item for item in items if item.fields["activity"] == ref
                           and item.fields["learner"] == learner_ref.model_dump()
                           and item.fields.get("processNode") == occurrence.ref.model_dump()]
                inputs[ref["id"]] = derive_activity_status(matches[-1], snapshot, bindings) if matches else "NOT_STARTED"
    else:
        inputs = {"evidence": occurrence.fields["evidence"]}
    return "COMPLETED" if evaluate_rule(EntityRef.model_validate(rule), snapshot, inputs, bindings) == "SATISFIED" else "IN_PROGRESS"
