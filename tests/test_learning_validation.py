import unittest

from learning.context import Snapshot
from learning.rules import evaluate_rule
from learning.validation import validate_snapshot, check_readiness
from tests.learning_fixtures import load_bundle, record, ref


def snapshot(*entities):
    bundle = load_bundle()
    from learning.metamodel import load_contract
    contract = load_contract()
    profiles = [e.ref.model_dump() for e in entities if e.type != "DomainModel"
                and contract.entity_types[e.type]["instanceLayer"] == "domain_configuration"]
    if profiles:
        bundle = tuple(e.model_copy(update={"fields": {**e.fields, "definitions": profiles}})
                       if e.type == "DomainModel" else e for e in bundle)
    context = next(e for e in bundle if e.type == "ExecutionContext")
    return Snapshot(context, "1", {e.ref: e for e in (*bundle, *entities)})


class ValidationTest(unittest.TestCase):
    def test_associative_cycles_allowed_hierarchy_cycles_rejected(self):
        a = record("Topic", "a", {"name": "a", "definition": "A", "relatedTopics": [ref("Topic", "b")]})
        b = record("Topic", "b", {"name": "b", "definition": "B", "relatedTopics": [ref("Topic", "a")]})
        self.assertFalse(validate_snapshot(snapshot(a, b)))
        a = record("Topic", "a", {**a.fields, "parentTopics": [ref("Topic", "b")]})
        b = record("Topic", "b", {**b.fields, "parentTopics": [ref("Topic", "a")]})
        self.assertIn("R04", [f.code for f in validate_snapshot(snapshot(a, b))])

    def test_unbound_text_rule_is_unknown(self):
        rule = record("RuleDefinition", "rule", {"purpose": "Acquisizione", "inputs": ["answer"],
            "condition": "Una risposta corretta", "outcome": "Acquisito", "unknownBehavior": "UNKNOWN",
            "approvalRequirement": "Politica vigente"})
        self.assertEqual(evaluate_rule(rule.ref, snapshot(rule), {"answer": "plausible"}, {}), "UNKNOWN")
        self.assertEqual(evaluate_rule(rule.ref, snapshot(rule), {}, {rule.ref: lambda _: "SATISFIED"}), "UNKNOWN")

    def test_unknown_mandatory_blocks_recommendation_warns(self):
        outcome = record("LearningOutcome", "outcome", {"statement": "Comprendere", "topics": [ref("Topic", "topic")]})
        activity = record("ActivityDefinition", "activity", {"instruction": "Spiega", "intent": "EXPLAIN",
            "format": "EXPOSITION", "outcomes": [outcome.ref.model_dump()]})
        prerequisite = record("Prerequisite", "prereq", {"dependent": activity.ref.model_dump(),
            "requiredTarget": outcome.ref.model_dump(), "kind": "MANDATORY"})
        findings = check_readiness(snapshot(outcome, activity, prerequisite), activity.ref, "interact")
        self.assertTrue(any(f.code == "R05" and f.severity == "BLOCKING" for f in findings))
        recommendation = record("Prerequisite", "prereq", {**prerequisite.fields, "kind": "RECOMMENDED"})
        self.assertEqual([f.severity for f in check_readiness(snapshot(outcome, activity, recommendation), activity.ref, "interact")], ["WARNING"])

    def test_empty_unit_is_valid_draft_but_not_ready(self):
        outcome = record("LearningOutcome", "outcome", {"statement": "Comprendere", "topics": [ref("Topic", "topic")]})
        unit = record("ProcessNode", "unit", {"name": "unit", "kind": "UNIT", "outcomes": [outcome.ref.model_dump()]})
        self.assertFalse(validate_snapshot(snapshot(outcome, unit)))
        self.assertTrue(check_readiness(snapshot(outcome, unit), unit.ref, "interact"))

    def test_domain_definitions_cannot_own_state(self):
        model = record("DomainModel", "bad", {"name": "bad", "scope": "scope", "topics": [ref("Topic", "topic")],
            "definitions": [ref("ExecutionContext", "session")]})
        self.assertIn("R02", [f.code for f in validate_snapshot(snapshot(model))])

    def test_duplicate_rubric_keys_rejected(self):
        level = {"key": "ok", "descriptor": "Descrizione"}
        criterion = {"key": "same", "outcomes": [ref("LearningOutcome", "outcome")], "description": "Criterio", "levels": [level]}
        rubric = record("Rubric", "rubric", {"name": "Rubrica", "criteria": [criterion, criterion]})
        self.assertIn("R10", [f.code for f in validate_snapshot(snapshot(rubric))])
