from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from learning.assessment import record_attempt, validate_evaluation, derive_learning_state, derive_activity_status
from learning.contracts import EntityRef
from learning.context import LearningRequest, RunContext, load_context
from learning.metamodel import load_contract
from learning.rules import answer_key_match
from learning.store import LearningStore, StateConflict
from tests.learning_fixtures import record, ref
from tests.test_learning_context import policy
from tests.test_learning_decisions import admin_bundle


def assessment_bundle():
    base = list(admin_bundle())
    rule = record("RuleDefinition", "achievement", {"purpose": "Exact answer", "inputs": ["answers", "answer_key"],
        "condition": "Answer matches the key after trimming surrounding whitespace", "outcome": "Acquired if correct",
        "unknownBehavior": "UNKNOWN", "approvalRequirement": "Current policy"})
    outcome = record("LearningOutcome", "outcome", {"statement": "Calculate 2+2", "topics": [ref("Topic", "topic")],
        "achievementRule": rule.ref.model_dump(), "verificationRule": rule.ref.model_dump()})
    activity = record("ActivityDefinition", "activity", {"instruction": "What is 2+2?", "intent": "ASSESS",
        "format": "SHORT_STRUCTURED", "outcomes": [outcome.ref.model_dump()], "expectedEvidence": ["OBJECTIVE_RESPONSE"],
        "assessmentSpec": ref("AssessmentSpecification", "assessment")})
    specification = record("AssessmentSpecification", "assessment", {"outcomes": [outcome.ref.model_dump()],
        "activities": [activity.ref.model_dump()], "allowedEvidence": ["OBJECTIVE_RESPONSE"], "answerKey": "4",
        "decisionRule": rule.ref.model_dump()})
    extras = (rule, outcome, activity, specification)
    base = [record(e.type, e.id, {**e.fields, "outcomes": [outcome.ref.model_dump()],
            "definitions": [item.ref.model_dump() for item in extras]}) if e.type == "DomainModel" else e for e in base]
    return tuple([*base, *extras])


class AssessmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = LearningStore(Path(self.temp.name) / "state.sqlite"); self.addCleanup(self.store.close)
        self.store.seed(assessment_bundle(), owner="session")

    def context(self, subject="learner"):
        request = LearningRequest(request_id="req", context_ref=self.store.read_context("session").ref,
                                  subject_key=subject, text="Response", intent="ASSESS")
        snap = load_context(self.store, request, policy(), load_contract())
        return RunContext(snap, policy(), load_contract(), request, snap.get(ref("Participant", subject)))

    def evaluation(self, evidence, mode="FORMATIVE"):
        return record("Evaluation", "evaluation", {"context": evidence.fields["context"],
            "evidence": [evidence.ref.model_dump()], "specification": ref("AssessmentSpecification", "assessment"),
            "mode": mode, "result": "Correct answer", "reviewPayloadKey": "pending"})

    def test_attempt_is_observed_and_survives_reopen(self):
        evidence = record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="attempt")
        self.assertEqual(evidence.provenance.origin, "OBSERVED_EVENT")
        with LearningStore(Path(self.temp.name) / "state.sqlite") as reopened:
            self.assertEqual(reopened.read(evidence.ref, owner="session").fields["contentOrLocator"], "4")
        self.assertEqual(record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="attempt"), evidence)
        with self.assertRaises(StateConflict):
            record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "5", request_id="attempt")

    def test_retired_activity_cannot_accept_new_attempt(self):
        evidence = record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="old")
        root = self.store.read_context("session")
        model = self.store.read(EntityRef.model_validate(ref("DomainModel", "model")), owner="session")
        revised_model = record("DomainModel", "model", {**model.fields,
            "definitions": [item for item in model.fields["definitions"]
                            if item["type"] not in {"ActivityDefinition", "AssessmentSpecification"}]}, "2")
        revised_root = record("ExecutionContext", "session", {**root.fields,
            "models": [revised_model.ref.model_dump()]}, "retired")
        change = record("StateChange", "retire-activity", {
            "context": root.ref.model_dump(), "baseVersion": root.version, "newVersion": revised_root.version,
            "cause": evidence.ref.model_dump(), "authorizationBasis": "test",
            "change": "Retire activity", "recordedAt": "2026-10-29T12:00:00+00:00"})
        self.store.commit_change(change, (revised_model, revised_root),
                                 expected_version=root.version, operation_id="retire")
        self.assertEqual(record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"),
                                        "4", request_id="old"), evidence)
        with self.assertRaisesRegex(ValueError, "active model"):
            record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="new")

    def test_unmet_mandatory_prerequisite_blocks_attempt(self):
        root = self.store.read_context("session")
        model = self.store.read(EntityRef.model_validate(ref("DomainModel", "model")), owner="session")
        prerequisite = record("Prerequisite", "required", {
            "dependent": ref("ActivityDefinition", "activity"),
            "requiredTarget": ref("LearningOutcome", "outcome"), "kind": "MANDATORY"})
        revised_model = record("DomainModel", "model", {**model.fields,
            "definitions": [*model.fields["definitions"], prerequisite.ref.model_dump()]}, "2")
        revised_root = record("ExecutionContext", "session", {**root.fields,
            "models": [revised_model.ref.model_dump()]}, "2")
        change = record("StateChange", "add-prerequisite", {
            "context": root.ref.model_dump(), "baseVersion": root.version, "newVersion": "2",
            "cause": root.ref.model_dump(), "authorizationBasis": "test",
            "change": "Require prerequisite", "recordedAt": "2026-10-29T12:00:00+00:00"})
        self.store.commit_change(change, (prerequisite, revised_model, revised_root),
                                 expected_version=root.version, operation_id="add-prerequisite")
        with self.assertRaisesRegex(ValueError, "not ready"):
            record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="new")

    def test_acquired_does_not_imply_verified(self):
        evidence = record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="attempt")
        evaluation = self.evaluation(evidence, "FORMAL")
        context = self.context()
        bindings = {context.snapshot.get(ref("RuleDefinition", "achievement")).ref: answer_key_match}
        state = derive_learning_state(context, evaluation, bindings)
        self.assertEqual(state.fields["progress"], "ACQUIRED")
        self.assertEqual(state.fields["verification"], "PENDING_CONFIRMATION")

    def test_missing_rule_does_not_invent_a_result(self):
        evidence = record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="attempt")
        state = derive_learning_state(self.context(), self.evaluation(evidence), {})
        self.assertEqual(state.fields["progress"], "IN_PROGRESS")
        self.assertEqual(state.fields["verification"], "UNVERIFIED")

    def test_missing_or_generated_evidence_is_not_assessment(self):
        evidence = record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="attempt")
        context = self.context()
        missing = self.evaluation(evidence).model_copy(update={"fields": {**self.evaluation(evidence).fields, "evidence": []}})
        self.assertTrue(validate_evaluation(missing, context.snapshot))
        generated = evidence.model_copy(update={"provenance": evidence.provenance.model_copy(update={"origin": "GENERATED_PROPOSAL"})})
        snap = replace(context.snapshot, entities={**context.snapshot.entities, generated.ref: generated})
        self.assertTrue(validate_evaluation(self.evaluation(evidence), snap))

    def test_completed_worker_does_not_complete_activity(self):
        evidence = record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="attempt")
        snap = self.context().snapshot
        occurrence = snap.get(evidence.fields["occurrence"])
        self.assertEqual(derive_activity_status(occurrence, snap, {}), "IN_PROGRESS")

    def test_occurrence_and_evidence_must_agree(self):
        evidence = record_attempt(self.store, self.context(), ref("ActivityDefinition", "activity"), "4", request_id="attempt")
        context = self.context()
        altered = evidence.model_copy(update={"fields": {**evidence.fields, "learner": ref("Participant", "admin")}})
        snap = replace(context.snapshot, entities={**context.snapshot.entities, altered.ref: altered})
        self.assertTrue(validate_evaluation(self.evaluation(evidence), snap))

    def test_new_specification_does_not_reinterpret_history(self):
        evidence = record_attempt(self.store,self.context(),ref('ActivityDefinition','activity'),'4',request_id='attempt')
        context = self.context()
        original = context.snapshot.get(ref('AssessmentSpecification','assessment'))
        revised = original.model_copy(update={'version':'2','fields':{**original.fields,'answerKey':'5'}})
        evaluation = self.evaluation(evidence).model_copy(update={'fields':{**self.evaluation(evidence).fields,'specification':revised.ref.model_dump()}})
        snap = replace(context.snapshot,entities={**context.snapshot.entities,revised.ref:revised})
        self.assertTrue(validate_evaluation(evaluation,snap))

    def test_formal_application_derives_verified_only_with_bound_rules(self):
        from learning.policies import RuleBinding
        from learning.decisions import create_proposal, save_proposal, record_decision, apply_proposal
        evidence = record_attempt(self.store,self.context(),ref('ActivityDefinition','activity'),'4',request_id='attempt')
        context = self.context('admin')
        trusted = context.policy.model_copy(update={'rule_bindings':[RuleBinding(rule=EntityRef.model_validate(ref('RuleDefinition','achievement')),handler='answer_key_match')]})
        snapshot = load_context(self.store,context.request,trusted,context.contract)
        context = replace(context,policy=trusted,snapshot=snapshot)
        evaluation = self.evaluation(evidence,'FORMAL')
        proposal = create_proposal(context,(context.snapshot.context.ref,),(evaluation,),'Confirm performance')
        save_proposal(self.store,context,proposal,(evaluation,))
        record_decision(self.store,context,proposal.ref,'APPROVE','Evidence reviewed')
        apply_proposal(self.store,context,proposal.ref,operation_id='assessment')
        root = self.store.read_context('session')
        state = self.store.read(EntityRef.model_validate(root.fields['learningStates'][0]),owner='session')
        self.assertEqual((state.fields['progress'],state.fields['verification']),('ACQUIRED','VERIFIED'))
