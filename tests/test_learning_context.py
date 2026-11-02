from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from learning.context import LearningRequest, load_context
from learning.policies import TrustedPolicy, authorize
from learning.store import LearningStore
from learning.metamodel import load_contract
from tests.learning_fixtures import load_bundle, record, ref


def policy():
    return TrustedPolicy.model_validate({"policy_ref": ref("PolicySet", "policy"), "subjects": {
        "learner": {"roles": ["LEARNER"], "actions": {"session": ["read", "interact", "submit"]}},
        "admin": {"roles": ["ADMINISTRATOR", "CONTENT_RESPONSIBLE", "ASSESSOR"],
                  "actions": {"session": ["read", "interact", "propose", "decide", "apply", "bootstrap", "submit"]}}}})


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = LearningStore(Path(self.temp.name) / "state.sqlite"); self.addCleanup(self.store.close)
        self.store.seed(load_bundle(), owner="session")
        self.request = LearningRequest(request_id="request", context_ref=ref("ExecutionContext", "session"),
                                       subject_key="learner", text="Explain the topic")

    def load(self, request=None):
        return load_context(self.store, request or self.request, policy(), load_contract())

    def test_missing_identity_stops_before_ai(self):
        with self.assertRaises(ValueError):
            self.load(self.request.model_copy(update={"subject_key": "outsider"}))

    def test_role_without_grant_is_denied(self):
        with self.assertRaises(ValueError):
            authorize(policy(), "learner", "decide", self.request.context_ref)

    def test_historical_reference_uses_exact_version(self):
        self.store.seed((record("Topic", "topic", {"name": "New", "definition": "New version"}, "2"),))
        snapshot = self.load()
        self.assertEqual(snapshot.get(ref("Topic", "topic")).fields["name"], "Basic concepts")
        self.assertNotIn("2", [e.version for e in snapshot.entities.values() if e.type == "Topic"])

    def test_cross_context_evidence_is_denied(self):
        foreign = record("Participant", "other", {"subjectKey": "other", "roles": ["LEARNER"]})
        self.store.seed((foreign,), owner="other-session")
        request = self.request.model_copy(update={"references": (foreign.ref,)})
        snapshot = self.load(request)
        self.assertNotIn(foreign.ref, snapshot.entities)
        self.assertTrue(snapshot.findings)

    def test_unrelated_missing_model_does_not_block_request(self):
        snapshot = self.load()
        self.assertFalse(snapshot.findings)
        self.assertEqual(snapshot.base_version, "1")

    def test_active_learning_requires_model_and_policy_version(self):
        context = self.store.read_context("session")
        invalid = record("ExecutionContext", "empty", {**context.fields, "models": []})
        self.store.seed((invalid,), owner="empty")
        configured = policy().model_dump()
        configured["subjects"]["learner"]["actions"]["empty"] = ["read"]
        request = self.request.model_copy(update={"context_ref": invalid.ref})
        with self.assertRaises(ValueError):
            load_context(self.store, request, TrustedPolicy.model_validate(configured), load_contract())
