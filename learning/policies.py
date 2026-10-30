from pathlib import Path
import json
from typing import Literal

from pydantic import Field

from learning.contracts import EntityRef, Record, Text


HumanRole = Literal["LEARNER", "CONTENT_RESPONSIBLE", "ASSESSOR", "OBSERVER", "ADMINISTRATOR"]
Action = Literal["read", "interact", "submit", "propose", "decide", "apply", "bootstrap"]


class SubjectGrant(Record):
    roles: list[HumanRole]
    actions: dict[Text, list[Action]]


class ScopeGrant(Record):
    contexts: list[Text]
    subjects: list[Text]
    activities: list[Text] = Field(default_factory=list)
    resources: list[Text] = Field(default_factory=list)
    sources: list[Text] = Field(default_factory=list)
    operations: list[Text] = Field(default_factory=lambda: ["read"])


class RuleBinding(Record):
    rule: EntityRef
    handler: Literal["answer_key_match", "all_true", "all_completed"]


class TrustedPolicy(Record):
    policy_ref: EntityRef
    subjects: dict[Text, SubjectGrant]
    scopes: dict[Text, ScopeGrant] = Field(default_factory=dict)
    rule_bindings: list[RuleBinding] = Field(default_factory=list)


def load_trusted_policy(path: Path, policy_ref: EntityRef) -> TrustedPolicy:
    policy = TrustedPolicy.model_validate(json.loads(path.read_text()))
    if policy.policy_ref != policy_ref or policy_ref.type != "PolicySet":
        raise ValueError("Trusted policy version mismatch")
    return policy


def authorize(policy: TrustedPolicy, subject_key: str, action: str, context_ref: EntityRef) -> None:
    subject = policy.subjects.get(subject_key)
    if context_ref.type != "ExecutionContext" or subject is None or action not in subject.actions.get(context_ref.id, []):
        raise ValueError("Action is not authorized in this context")


def scope_allows(policy: TrustedPolicy, name: str, context_id: str, subject: str,
                 activity_ids: tuple[str, ...] = ()) -> bool:
    scope = policy.scopes.get(name)
    return bool(scope and context_id in scope.contexts and subject in scope.subjects
                and "read" in scope.operations
                and (not scope.activities or (activity_ids and set(activity_ids) <= set(scope.activities))))
