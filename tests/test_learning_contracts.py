import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from learning.metamodel import load_contract, validate_entity, lead_contract


SPEC = Path(__file__).resolve().parents[1] / "docs/resources/metamodello-agnostico-apprendimento.json"


def topic():
    return {"type": "Topic", "id": "Topic-A", "version": "1", "provenance": {
        "origin": "CONFIGURATION", "sources": [], "responsible": "admin"},
        "fields": {"name": "Argomento", "definition": "Definizione"}}


class ContractTest(unittest.TestCase):
    def setUp(self):
        self.contract = load_contract(SPEC)

    def test_fixed_contract_and_all_descriptors(self):
        original = SPEC.read_bytes()
        self.assertEqual(self.contract.version, "1.0.0")
        self.assertEqual(len(self.contract.entity_types), 29)
        self.assertEqual(len(self.contract.value_types), 8)
        entity = validate_entity(topic(), self.contract)
        self.assertEqual(entity.fields["parentTopics"], [])
        self.assertEqual(entity.ref.id, "Topic-A")
        self.assertEqual(SPEC.read_bytes(), original)
        self.assertEqual(hashlib.sha256(original).hexdigest(), self.contract.digest)

    def test_changed_contract_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "contract.json"
            path.write_bytes(SPEC.read_bytes() + b"\n")
            with self.assertRaises(ValueError):
                load_contract(path)

    def test_invalid_fields_types_enums_and_references(self):
        invalid = []
        for name, value in (("name", ""), ("name", 12), ("parentTopics", ["Topic-A"]),
                            ("parentTopics", [{"type": "Resource", "id": "x", "version": "1"}]),
                            ("newField", "extra"), ("definition", None)):
            item = topic()
            item["fields"][name] = value
            invalid.append(item)
        item = topic(); item["provenance"]["origin"] = "INVENTED"; invalid.append(item)
        item = topic(); del item["fields"]["name"]; invalid.append(item)
        item = topic(); item["extra"] = True; invalid.append(item)
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_entity(item, self.contract)

    def test_boolean_has_no_numeric_coercion(self):
        ref = lambda name: {"type": name, "id": name, "version": "1"}
        item = topic() | {"type": "ResourceBinding", "fields": {
            "context": ref("ExecutionContext"), "resource": ref("Resource"),
            "usageScope": "lesson", "valid": 1, "reviewPayloadKey": "key"}}
        with self.assertRaises(ValueError):
            validate_entity(item, self.contract)
        item["fields"]["valid"] = True
        self.assertTrue(validate_entity(item, self.contract).fields["valid"])

    def test_projection_keeps_global_rules_and_is_deterministic(self):
        text = lead_contract(self.contract, frozenset({"SOCRATIC"}))
        self.assertIn("R19", text)
        self.assertIn("ARC_NO_WRITE", text)
        self.assertIn("SOCRATIC", text)
        self.assertEqual(text, lead_contract(self.contract, frozenset({"SOCRATIC"})))

    def test_validation_does_not_mutate_input(self):
        item = topic(); original = copy.deepcopy(item)
        validate_entity(item, self.contract)
        self.assertEqual(item, original)

    def test_minimal_bundle_has_model_and_context(self):
        from tests.learning_fixtures import load_bundle
        self.assertEqual({item.type for item in load_bundle()},
                         {"Topic", "DomainModel", "PolicySet", "Participant", "ExecutionContext"})
