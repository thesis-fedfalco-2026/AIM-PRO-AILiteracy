import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from aimpro.audit import DEFAULT_PROJECT
from aimpro.contracts import Contracts
from aimpro.generate import generate
from aimpro.validation import validate_scenario


class AimproContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = Contracts()

    def key(self, package, name):
        matches = [key for key in self.contracts.classes if key[1:] == (package, name)]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_all_classes_and_concrete_schemas_are_generated(self):
        self.assertEqual(len(self.contracts.classes), 82)
        self.assertEqual(len(self.contracts.schemas()), 67)
        self.assertTrue(generate(check=True))

    def test_same_named_classes_remain_distinct(self):
        isqd = self.key("iSQD", "Scenario")
        delivery = self.key("Scenario", "Scenario")
        self.assertIsNot(self.contracts.classes[isqd], self.contracts.classes[delivery])
        self.assertNotEqual(isqd[0], delivery[0])

    def test_inherited_aliases_and_multiple_inheritance(self):
        practice = self.key("iSQD", "ModellingAIPractices")
        self.assertTrue(self.contracts.is_subtype(practice, self.key("iSQD", "Activity")))
        self.assertTrue(self.contracts.is_subtype(practice, self.key("iSQD", "AFamiliarization")))
        cls = self.contracts.classes[practice]
        value = cls.model_validate({"inPractice": "Example", "rationale": "Reason"})
        self.assertEqual(value.model_dump(by_alias=True)["inPractice"], "Example")
        with self.assertRaises(ValidationError):
            cls.model_validate({"unknown": "value"})

    def test_source_estring_is_not_replaced_by_enum(self):
        cls = self.contracts.classes[self.key("Competencies", "Competency")]
        value = cls.model_validate({"category": "Digital", "ksa": "SKILL",
                                    "proficiency": "FOUNDATION", "sourceFrameworks": ["OECD"]})
        self.assertEqual(value.model_dump(by_alias=True)["ksa"], "SKILL")
        for patch in ({"category": "DIGITAL"}, {"category": 1}, {"sourceFrameworks": []}):
            data = value.model_dump(by_alias=True) | patch
            with self.assertRaises(ValidationError):
                cls.model_validate(data)

    def test_primitive_strictness(self):
        cls = self.contracts.classes[self.key("sustainability", "DeviceContext")]
        for data in ({"supportsRAPL": 1}, {"ramGb": "16"}, {"ramGb": float("inf")}):
            with self.assertRaises(ValidationError):
                cls.model_validate(data)
        cls.model_validate({"supportsRAPL": True, "ramGb": 16.0})

    def test_real_source_is_preserved_and_incomplete(self):
        before = DEFAULT_PROJECT.read_bytes()
        report = validate_scenario()
        self.assertFalse(report["conforms_to_generated_contracts"])
        self.assertEqual(len(report["findings"]), 5)
        self.assertEqual(len(report["transport_conversions"]), 2)
        self.assertEqual(len(report["validated_objects"]), 5)
        self.assertEqual(DEFAULT_PROJECT.read_bytes(), before)

    def test_reference_type_and_containment_are_checked(self):
        project = json.loads(DEFAULT_PROJECT.read_bytes())
        root = next(m for m in project["definitions"]["models"]
                    if m["metadata"]["name"] == "SCN01")["objects"][0]
        learner = root["children"].pop("learner")[0]
        root["references"] = {"learner": [{"$ref": root["id"]}]}
        # Keep the original learner owned, but its role in this graph is deliberately wrong.
        next(m for m in project["definitions"]["models"]
             if m["metadata"]["name"] == "SCN01")["objects"].append(learner)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(project), encoding="utf-8")
            report = validate_scenario(path)
        self.assertTrue(any(f["code"] == "REFERENCE_TYPE" for f in report["findings"]))
        self.assertTrue(any(f["code"] == "CONTAINMENT_SECTION" for f in report["findings"]))

    def test_fingerprint_and_artifact_drift_detection(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "generated"
            generate(output=target)
            self.assertTrue(generate(output=target, check=True))
            (target / "manifest.json").write_text("{}", encoding="utf-8")
            self.assertFalse(generate(output=target, check=True))
            project = json.loads(DEFAULT_PROJECT.read_bytes())
            project["definitions"]["metamodels"][0]["packages"][0]["classes"][0]["attributes"][1]["lowerBound"] = 0
            source = Path(directory) / "project.json"
            source.write_text(json.dumps(project), encoding="utf-8")
            self.assertNotEqual(Contracts(source).fingerprint, self.contracts.fingerprint)

    def test_duplicate_types_and_inheritance_cycles_fail(self):
        for cycle in (False, True):
            project = json.loads(DEFAULT_PROJECT.read_bytes())
            package = project["definitions"]["metamodels"][0]["packages"][0]
            if cycle:
                package["classes"][1]["superTypes"] = [{"name": "Competency", "package": "Competencies"}]
            else:
                package["classes"].append(package["classes"][0])
            with TemporaryDirectory() as directory:
                path = Path(directory) / "project.json"
                path.write_text(json.dumps(project), encoding="utf-8")
                with self.assertRaises(ValueError):
                    Contracts(path)

    def test_external_field_names_are_aliases_never_python_code(self):
        project = json.loads(DEFAULT_PROJECT.read_bytes())
        package = project["definitions"]["metamodels"][0]["packages"][0]
        package["classes"].append({"name": "not-valid-python()", "attributes": [
            {"name": "class", "type": "EString", "lowerBound": 1}]})
        with TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(project), encoding="utf-8")
            contracts = Contracts(path)
        cls = next(cls for key, cls in contracts.classes.items() if key[2] == "not-valid-python()")
        self.assertEqual(cls.model_validate({"class": "data"}).model_dump(by_alias=True), {"class": "data"})
