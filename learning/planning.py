from dataclasses import dataclass
from typing import Literal

from agent_system.config import OrchestratorSettings
from agent_system.plan import PlanStep, ExecutionPlan, validate_and_order_plan
from agent_system.registry import AgentRegistry
from document_search.contracts import SearchScope, resource_key
from learning.contracts import Entity, EntityRef, Record, Text, make_entity
from learning.context import Snapshot, RunContext
from learning.policies import TrustedPolicy, scope_allows
from learning.store import canonical
from learning.validation import check_readiness


ROLE_CONTRACTS = {
    "TEACHER": ("TEACHER_TRAINER", "EXPLAIN", {"EXPLANATION"}),
    "TRAINER": ("TEACHER_TRAINER", "PRACTICE", {"GUIDED_PRACTICE"}),
    "CURATOR": ("CURATOR", "CURATE", {"SUPPORT_MATERIAL", "CHANGE_PROPOSAL"}),
    "EVALUATOR": ("EVALUATOR", "ASSESS", {"ASSESSMENT", "CHANGE_PROPOSAL"}),
    "SOCRATIC": ("SOCRATIC", "SOCRATIC_GUIDANCE", {"SOCRATIC_TURN"}),
}


class LegacyAgentReferenceError(ValueError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Legacy registryName {name!r}: migrate the specialization to a renamed agent")


def eligible_specializations(snapshot: Snapshot, registry: AgentRegistry,
                              policy: TrustedPolicy) -> tuple[Entity, ...]:
    eligible = []
    for specialization in snapshot.active_domain():
        if specialization.type != "AgentSpecialization":
            continue
        fields = specialization.fields
        role = ROLE_CONTRACTS.get(fields["role"])
        if not role or fields["category"] != role[0]:
            continue
        try:
            config = registry.get(fields["registryName"])
        except ValueError:
            legacy = {"teacher", "trainer", "socratic", "curator", "evaluator",
                      "learning-teacher", "learning-trainer", "learning-socratic",
                      "learning-curator", "learning-evaluator",
                      "agent-u", "agent-v", "agent-w", "agent-x", "agent-y", "agent-z"}
            if fields["registryName"] in legacy:
                raise LegacyAgentReferenceError(fields["registryName"]) from None
            continue
        try:
            for topic in fields["topics"]:
                snapshot.get(topic)
        except ValueError:
            continue
        if config.category != fields["role"].lower():
            continue
        if config.mode is not None and config.mode != snapshot.context.fields["mode"]:
            continue
        if set(config.tools) - {"search_documents"} or set(config.skills) - set(fields["skills"]):
            continue
        eligible.append(specialization)
    return tuple(eligible)


class Capability(Record):
    capability: Text
    accessPath: Literal["ORCHESTRATOR_RETRIEVAL", "WORKER_TOOL"]
    operations: tuple[Text, ...]
    scope: Text
    purpose: Text


class LearningStepDraft(Record):
    step: PlanStep
    specialization: EntityRef
    intent: Literal["EXPLAIN", "PRACTICE", "CURATE", "ASSESS", "SOCRATIC_GUIDANCE"]
    activities: tuple[EntityRef, ...] = ()
    required_capabilities: tuple[Capability, ...] = ()
    expected_output: Literal["EXPLANATION", "GUIDED_PRACTICE", "SUPPORT_MATERIAL", "ASSESSMENT", "SOCRATIC_TURN", "CHANGE_PROPOSAL"]
    coverage: tuple[EntityRef, ...] = ()


class LearningPlanDraft(Record):
    steps: tuple[LearningStepDraft, ...] = ()


@dataclass(frozen=True)
class AuthorizedTask:
    step: PlanStep
    record: Entity
    specialization: Entity
    expected_output: str
    coverage: tuple[EntityRef, ...]
    search_scope: SearchScope
    resources: tuple[Entity, ...]
    context: RunContext
    evidence: dict | None = None


def _scope(context: RunContext, draft: LearningStepDraft) -> tuple[SearchScope, tuple[Entity, ...]]:
    snap, policy = context.snapshot, context.policy
    names = {cap.scope for cap in draft.required_capabilities}
    activities = tuple(ref.id for ref in draft.activities)
    permitted = [name for name in names if scope_allows(policy, name, snap.context.id,
                                                       context.request.subject_key, activities)]
    mode = snap.context.fields["mode"]
    if mode == "PREPARATION":
        return SearchScope(mode=mode, source_scope_keys=tuple(sorted({source for name in permitted
            for source in policy.scopes[name].sources}))), ()
    from learning.decisions import approval_valid
    resources = {}
    bound_refs = {EntityRef.model_validate(ref) for ref in snap.context.fields["resourceBindings"]}
    for binding in snap.of_type("ResourceBinding"):
        if binding.ref not in bound_refs or not binding.fields["valid"] or binding.fields["usageScope"] not in permitted:
            continue
        if not approval_valid(binding, snap, policy):
            continue
        resource = snap.get(binding.fields["resource"])
        key = resource_key(resource.id, resource.version)
        if key not in policy.scopes[binding.fields["usageScope"]].resources:
            continue
        if context.request.topic_refs and not set(context.request.topic_refs) & {EntityRef.model_validate(t) for t in resource.fields["topics"]}:
            continue
        resources[key] = resource
    return SearchScope(mode=mode, resource_keys=tuple(sorted(resources))), tuple(resources.values())


def authorize_plan(draft: LearningPlanDraft, context: RunContext, registry: AgentRegistry,
                   *, settings: OrchestratorSettings | None = None) -> tuple[AuthorizedTask, ...]:
    requested_activities = set(context.request.activity_refs) | {
        ref for ref in context.request.references if ref.type == "ActivityDefinition"}
    if not requested_activities <= {ref for step in draft.steps for ref in step.activities}:
        raise ValueError("Plan omits a requested activity")
    if not draft.steps and context.request.intent not in {"CLARIFICATION", "STATE"}:
        raise ValueError("A didactic request requires specialist delegation")
    ordered = validate_and_order_plan(ExecutionPlan(steps=tuple(item.step for item in draft.steps)),
                                      registry, settings or OrchestratorSettings(max_steps=6))
    eligible = {item.ref: item for item in eligible_specializations(context.snapshot, registry, context.policy)}
    drafts = {item.step.id: item for item in draft.steps}
    request_key = canonical([context.snapshot.context.id, context.request.request_id])
    tasks = []
    for step in ordered:
        proposed = drafts[step.id]
        specialization = eligible.get(proposed.specialization)
        if specialization is None or specialization.fields["registryName"] != step.agent:
            raise ValueError("Specialization is unavailable")
        fields = specialization.fields
        _, intent, outputs = ROLE_CONTRACTS[fields["role"]]
        if proposed.intent != intent or proposed.expected_output not in outputs:
            raise ValueError("Task intent or output violates role")
        worker = registry.get(step.agent)
        if worker.mode is not None and (worker.mode != context.snapshot.context.fields["mode"] or worker.expected_output != proposed.expected_output):
            raise ValueError("Worker task contract does not match mode or output")
        if fields["role"] == "CURATOR" and proposed.expected_output == "CHANGE_PROPOSAL" and context.snapshot.context.fields["mode"] != "PREPARATION":
            raise ValueError("Curator CHANGE_PROPOSAL requires PREPARATION")
        if context.request.intent == "SOCRATIC_GUIDANCE" and intent != "SOCRATIC_GUIDANCE":
            raise ValueError("Active Socratic problem cannot disclose a solution")
        topics = {EntityRef.model_validate(ref) for ref in fields["topics"]}
        if not set(context.request.topic_refs) <= topics:
            raise ValueError("Requested topic is outside specialization")
        for outcome in proposed.coverage:
            entity = context.snapshot.get(outcome)
            if entity.type != "LearningOutcome" or not {EntityRef.model_validate(t) for t in entity.fields["topics"]} <= topics:
                raise ValueError("Outcome is outside specialization")
        for activity in proposed.activities:
            if activity not in {e.ref for e in context.snapshot.active_domain()}:
                raise ValueError("Activity is not in the active model")
            entity = context.snapshot.get(activity)
            if entity.type != "ActivityDefinition" or entity.fields["intent"] != intent:
                raise ValueError("Activity intent does not match task")
            if any(f.severity == "BLOCKING" for f in check_readiness(context.snapshot, activity, "interact",
                    learner_ref=context.participant.ref, policy=context.policy, subject_key=context.request.subject_key)):
                raise ValueError("Activity is not ready")
        grants = [Capability.model_validate(cap) for cap in fields["capabilities"]]
        for need in proposed.required_capabilities:
            if need.capability != "search_documents" or need.accessPath != "ORCHESTRATOR_RETRIEVAL" or set(need.operations) != {"read"}:
                raise ValueError("Unsupported task capability")
            if not any(need.capability == grant.capability and need.accessPath == grant.accessPath
                       and need.scope == grant.scope and set(need.operations) <= set(grant.operations) for grant in grants):
                raise ValueError("Capability exceeds specialization")
            if not scope_allows(context.policy, need.scope, context.snapshot.context.id, context.request.subject_key,
                                tuple(a.id for a in proposed.activities)):
                raise ValueError("Capability exceeds context policy")
        if step.retrieval and not proposed.required_capabilities:
            raise ValueError("Retrieval requires an authorized capability")
        if proposed.required_capabilities and not step.retrieval:
            raise ValueError("Unused capabilities are not necessary")
        scope, resources = (_scope(context, proposed) if step.retrieval else
                            (SearchScope(mode=context.snapshot.context.fields["mode"]), ()))
        if step.retrieval and not scope.keys:
            raise ValueError("No approved sources for this task")
        dependencies = [EntityRef(type="WorkerTask", id=f"{request_key}/task/{key}", version="1").model_dump()
                        for key in step.depends_on]
        record = make_entity("WorkerTask", f"{request_key}/task/{step.id}", {
            "stepKey": step.id, "specialization": specialization.ref.model_dump(), "intent": proposed.intent,
            "brief": step.task, "activities": [a.model_dump() for a in proposed.activities],
            "dependsOn": dependencies, "requiredCapabilities": [c.model_dump(mode="json") for c in proposed.required_capabilities],
            "expectedOutput": proposed.expected_output,
            **({"retrievalNeed": step.retrieval.query} if step.retrieval else {})}, origin="GENERATED_PROPOSAL")
        tasks.append(AuthorizedTask(step, record, specialization, proposed.expected_output,
                                    proposed.coverage, scope, resources, context))
    return tuple(tasks)
