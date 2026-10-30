from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from learning.context import LearningRequest, RunContext, load_context
from learning.decisions import (create_proposal, save_proposal, record_decision, apply_proposal,
                                review_payload_key, approval_valid)
from learning.metamodel import load_contract
from learning.store import LearningStore, StateConflict
from tests.learning_fixtures import load_bundle, record, ref
from tests.test_learning_context import policy


def admin_bundle():
    data = list(load_bundle())
    admin = record("Participant", "admin", {"subjectKey": "admin", "roles": ["ADMINISTRATOR", "CONTENT_RESPONSIBLE", "ASSESSOR"]})
    data = [record(e.type, e.id, {**e.fields, "participants": [*e.fields["participants"], admin.ref.model_dump()]})
            if e.type == "ExecutionContext" else e for e in data]
    return tuple([*data, admin])


class DecisionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = LearningStore(Path(self.temp.name) / "state.sqlite"); self.addCleanup(self.store.close)
        self.store.seed(admin_bundle(), owner="session")
        self.policy = policy()

    def context(self, subject="admin"):
        current = self.store.read_context("session")
        request = LearningRequest(request_id="request", context_ref=current.ref, subject_key=subject, text="Configura", intent="STATE")
        snap = load_context(self.store, request, self.policy, load_contract())
        return RunContext(snap, self.policy, load_contract(), request, snap.get(ref("Participant", subject)))

    def proposal(self, identity="new"):
        context = self.context()
        topic = record("Topic", identity, {"name": identity, "definition": "Nuovo argomento"})
        proposal = create_proposal(context, (context.snapshot.context.ref,), (topic,), "Aggiungere un topic")
        save_proposal(self.store, context, proposal, (topic,))
        return proposal

    def test_approval_and_apply_are_distinct_and_retry_is_idempotent(self):
        proposal = self.proposal()
        decision = record_decision(self.store, self.context(), proposal.ref, "APPROVE", "Esaminato")
        self.assertEqual(self.store.read_context("session").version, "1")
        with self.assertRaises(ValueError):
            self.store.read(record("Topic", "new", {"name": "new", "definition": "Nuovo argomento"}).ref, owner="session")
        changed = apply_proposal(self.store, self.context(), proposal.ref, operation_id="apply")
        self.assertNotEqual(self.store.read_context("session").version, "1")
        self.assertEqual(apply_proposal(self.store, self.context(), proposal.ref, operation_id="apply"), changed)
        self.assertEqual(decision.fields["reviewedPayloadKey"], proposal.fields["reviewPayloadKey"])

    def test_stale_proposal_does_not_apply(self):
        first, second = self.proposal("first"), self.proposal("second")
        for proposal in (first, second):
            record_decision(self.store, self.context(), proposal.ref, "APPROVE", "Esaminato")
        apply_proposal(self.store, self.context(), first.ref, operation_id="first")
        with self.assertRaises(StateConflict):
            apply_proposal(self.store, self.context(), second.ref, operation_id="second")
        self.assertEqual(next(e for e in self.store.owned("session", "ChangeProposal") if e.id == second.id).fields["status"], "STALE")

    def test_administrative_revision_keeps_reviewed_payload(self):
        proposal = self.proposal()
        record_decision(self.store, self.context(), proposal.ref, "APPROVE", "Esaminato")
        revised = self.store.owned("session", "ChangeProposal")[0]
        candidates = self.store.candidates(proposal.ref)
        self.assertNotEqual(revised.version, proposal.version)
        self.assertEqual(review_payload_key(revised, candidates), review_payload_key(proposal, candidates))

    def test_decision_cannot_grant_own_authority(self):
        proposal = self.proposal()
        with self.assertRaises(ValueError):
            record_decision(self.store, self.context("learner"), proposal.ref, "APPROVE", "Auto approvazione")

    def test_reject_and_revision_do_not_apply(self):
        for kind in ("REJECT", "REQUEST_REVISION"):
            proposal = self.proposal(kind.lower())
            record_decision(self.store, self.context(), proposal.ref, kind, "Correggere")
            with self.assertRaises(ValueError):
                apply_proposal(self.store, self.context(), proposal.ref, operation_id=kind)

    def test_added_candidate_is_not_covered(self):
        proposal = self.proposal()
        record_decision(self.store, self.context(), proposal.ref, "APPROVE", "Esaminato")
        extra = record("Topic", "extra", {"name": "extra", "definition": "Non esaminato"})
        self.store.append_candidates(proposal.ref, (extra,))
        with self.assertRaises(ValueError):
            apply_proposal(self.store, self.context(), proposal.ref, operation_id="tamper")

    def test_revoked_permission_blocks_apply(self):
        proposal = self.proposal()
        record_decision(self.store, self.context(), proposal.ref, "APPROVE", "Esaminato")
        revoked = self.policy.model_dump(); revoked["subjects"]["admin"]["actions"]["session"].remove("apply")
        self.policy = type(self.policy).model_validate(revoked)
        with self.assertRaises(ValueError):
            apply_proposal(self.store, self.context(), proposal.ref, operation_id="revoked")

    def test_binding_becomes_usable_only_after_review_and_application(self):
        context = self.context()
        resource = record("Resource", "book", {"title": "Libro", "contentOrLocator": "Materiale sintetico",
            "topics": [ref("Topic", "topic")], "usageConditions": "Uso didattico autorizzato"})
        binding = record("ResourceBinding", "binding", {"context": context.snapshot.context.ref.model_dump(),
            "resource": resource.ref.model_dump(), "usageScope": "lesson", "valid": True, "reviewPayloadKey": "pending"})
        model = context.snapshot.get(ref("DomainModel", "model"))
        model = record(model.type, model.id, {**model.fields, "definitions": [resource.ref.model_dump()]}, "2")
        root = record("ExecutionContext", "session", {**context.snapshot.context.fields,
            "models": [model.ref.model_dump()], "resourceBindings": [binding.ref.model_dump()]}, "2")
        candidates = (resource, binding, model, root)
        proposal = create_proposal(context, (context.snapshot.context.ref,), candidates, "Approvare materiale")
        save_proposal(self.store, context, proposal, candidates)
        self.assertFalse(approval_valid(binding, context.snapshot, self.policy))
        record_decision(self.store, self.context(), proposal.ref, "APPROVE", "Materiale esaminato")
        apply_proposal(self.store, self.context(), proposal.ref, operation_id="binding")
        applied = self.context().snapshot.get(binding.ref)
        self.assertTrue(approval_valid(applied, self.context().snapshot, self.policy))
        modified = applied.model_copy(update={"fields": {**applied.fields, "usageScope": "elsewhere"}})
        self.assertFalse(approval_valid(modified, self.context().snapshot, self.policy))

    def test_optional_defaults_do_not_change_reviewed_payload_on_storage(self):
        from learning.contracts import make_entity
        topic=make_entity('Topic','minimal-candidate',{'name':'Minimo','definition':'Default omessi'})
        context=self.context()
        proposal=create_proposal(context,(context.snapshot.context.ref,),(topic,),'Candidato minimale')
        save_proposal(self.store,context,proposal,(topic,))
        record_decision(self.store,context,proposal.ref,'APPROVE','Esaminato')
        change=apply_proposal(self.store,context,proposal.ref,operation_id='minimal')
        self.assertNotEqual(change.fields['newVersion'],context.snapshot.base_version)
