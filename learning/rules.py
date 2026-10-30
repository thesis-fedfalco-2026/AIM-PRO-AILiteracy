from collections.abc import Callable
from typing import Literal

from learning.contracts import EntityRef
from learning.context import Snapshot


TruthStatus = Literal["SATISFIED", "NOT_SATISFIED", "UNKNOWN"]
RuleBindings = dict[EntityRef, Callable[[dict], TruthStatus]]


def evaluate_rule(rule_ref: EntityRef, snapshot: Snapshot, inputs: dict,
                  bindings: RuleBindings) -> TruthStatus:
    try:
        rule = snapshot.get(rule_ref)
    except ValueError:
        return "UNKNOWN"
    if rule.type != "RuleDefinition" or rule_ref not in bindings:
        return "UNKNOWN"
    if any(name not in inputs or inputs[name] is None for name in rule.fields["inputs"]):
        return "UNKNOWN"
    try:
        result = bindings[rule_ref](inputs)
    except (ValueError, TypeError, KeyError):
        return "UNKNOWN"
    return result if result in {"SATISFIED", "NOT_SATISFIED", "UNKNOWN"} else "UNKNOWN"


def all_true(inputs: dict) -> TruthStatus:
    if not inputs or any(type(value) is not bool for value in inputs.values()):
        return "UNKNOWN"
    return "SATISFIED" if all(inputs.values()) else "NOT_SATISFIED"


def all_completed(inputs: dict) -> TruthStatus:
    if not inputs or any(value not in {"NOT_STARTED", "IN_PROGRESS", "COMPLETED", "SKIPPED"} for value in inputs.values()):
        return "UNKNOWN"
    return "SATISFIED" if all(value == "COMPLETED" for value in inputs.values()) else "NOT_SATISFIED"


def answer_key_match(inputs: dict) -> TruthStatus:
    answers, key = inputs.get("answers"), inputs.get("answer_key")
    if not isinstance(answers, list) or not answers or not isinstance(key, str):
        return "UNKNOWN"
    if any(not isinstance(answer, str) for answer in answers):
        return "UNKNOWN"
    return "SATISFIED" if all(answer.strip() == key.strip() for answer in answers) else "NOT_SATISFIED"
