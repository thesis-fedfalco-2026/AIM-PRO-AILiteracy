"""Regressions against the exact newer export, plus explicit invalid variants."""

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from aimpro.adapter import load_scenario
from aimpro.audit import DEFAULT_PROJECT, audit_project
from aimpro.change_requests import summary
from aimpro.contracts import Contracts
from aimpro.generate import generate
from aimpro.validation import validate_scenario


NEW_PROJECT = DEFAULT_PROJECT.with_name("aimpro-megamodel-2026-11-04.json")
NEW_SHA256 = "e2d842b6dc88dc9b40af6d848b67d001d940df82fc48dde88b259ca6878f253a"
NEW_OUTPUT = DEFAULT_PROJECT.parents[1] / "aimpro/generated-2026-11-04"
ALM_ID = "Pointer1793789994832_USER_35"


class AimproDataTypesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = Contracts(NEW_PROJECT)

    def altered_contracts(self, change):
        # These are negative/edge-case test variants, never substitute exports.
        project = json.loads(NEW_PROJECT.read_bytes())
        package = project["definitions"]["metamodels"][-1]["packages"][0]
        change(project, package)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "variant.json"
            path.write_text(json.dumps(project), encoding="utf-8")
            return Contracts(path)

    def domain(self, name):
        return self.contracts.classes[(ALM_ID, "alm", name)]

    def test_actual_export_hash_declarations_and_coverage(self):
        self.assertEqual(hashlib.sha256(NEW_PROJECT.read_bytes()).hexdigest(), NEW_SHA256)
        declarations = {key: value["instanceClassName"]
                        for key, value in self.contracts.data_types.items()}
        self.assertEqual(declarations, {
            (ALM_ID, "alm", name): "java.lang.String"
            for name in ("Identifier", "Text", "Version", "Timestamp", "Locator")
        } | {(ALM_ID, "alm", "Number"): "java.math.BigDecimal"})
        self.assertEqual(len(self.contracts.classes), 120)
        self.assertEqual(len(self.contracts.schemas()), 104)
        self.assertEqual(len(self.contracts.manifest()["data_types"]), 6)

    def test_strings_are_verbatim_not_inferred_from_alias_names(self):
        cls = self.domain("HumanDecision")
        data = dict(id="  not-a-uuid  ", version="not-semver", provenance="source-id",
                    decision="APPROVE", reason="  original text\n", decidedAt="not-a-date",
                    reviewedPayloadKey="payload", coveredPayloadKeys=["payload"],
                    context="context-id", decider="person-id", target="target-id")
        # Use the literal declared by the export, not a local decision vocabulary.
        decision = cls.model_json_schema(by_alias=True)["properties"]["decision"]["enum"][0]
        data["decision"] = decision
        self.assertEqual(cls.model_validate(data).model_dump(by_alias=True), data)
        for field in ("id", "version", "reason", "decidedAt"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                cls.model_validate(data | {field: 123})
        timestamp = cls.model_json_schema(by_alias=True)["properties"]["decidedAt"]
        self.assertEqual(timestamp["type"], "string")
        self.assertNotIn("format", timestamp)
        self.assertEqual(timestamp["aimpro"]["data_type"], [ALM_ID, "alm", "Timestamp"])

    def test_decimal_precision_finiteness_and_json_representation(self):
        cls = self.domain("RubricLevel")
        number = "12345678901234567890.12345678901234567890"
        for token in (number, '"' + number + '"', "1e-40", "123456789012345678901234567890"):
            with self.subTest(token=token):
                raw = '{"key":"level","descriptor":"original","score":' + token + '}'
                value = cls.model_validate_json(raw)
                expected = Decimal(token.strip('"'))
                self.assertEqual(value.model_dump(by_alias=True)["score"], expected)
                replay = cls.model_validate_json(value.model_dump_json(by_alias=True))
                self.assertEqual(replay.model_dump(by_alias=True)["score"], expected)
                schema = cls.model_json_schema(by_alias=True)["properties"]["score"]
                pattern = next(s["pattern"] for s in schema["anyOf"] if s.get("type") == "string")
                self.assertIsNotNone(re.fullmatch(pattern, json.loads(
                    value.model_dump_json(by_alias=True))["score"]))
        exact = Decimal(number)
        value = cls.model_validate(dict(key="level", descriptor="original", score=exact))
        self.assertEqual(value.model_dump(by_alias=True)["score"].as_tuple(), exact.as_tuple())
        for token in ("true", "[]", "{}", '"invalid"', '"NaN"', '"Infinity"', "NaN", "Infinity",
                      '"1_000"', '" 1.0 "'):
            with self.subTest(token=token), self.assertRaises(ValidationError):
                cls.model_validate_json('{"key":"k","descriptor":"d","score":' + token + '}')
        with self.assertRaises(ValidationError):
            cls.model_validate_json("invalid JSON")

    def test_inheritance_references_and_multiplicity_keep_source_identities(self):
        cls = self.domain("Rubric")
        schema = cls.model_json_schema(by_alias=True)
        self.assertEqual(schema["properties"]["id"]["aimpro"]["declared_by"],
                         [ALM_ID, "alm", "Entity"])
        reference = schema["properties"]["criteria"]
        self.assertEqual(reference["aimpro"]["target"], [ALM_ID, "alm", "RubricCriterion"])
        self.assertTrue(reference["aimpro"]["containment"])
        data = dict(id="id", version="version", provenance="provenance-id",
                    name="rubric", criteria=["exact-criterion-id"])
        self.assertEqual(cls.model_validate(data).model_dump(by_alias=True)["criteria"],
                         ["exact-criterion-id"])
        for patch in ({"criteria": []}, {"criteria": [""]},
                      {"criteria": [{"id": "inline-object"}]}, {"provenance": None}):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                cls.model_validate(data | patch)
        capability = self.domain("CapabilityGrant")
        data = dict(capability="cap", accessPath="WORKER_TOOL", operations=["read"],
                    scope="scope", purpose="purpose")
        capability.model_validate(data)
        with self.assertRaises(ValidationError):
            capability.model_validate(data | {"operations": []})

    def test_qualified_data_types_and_inherited_declaring_metamodel(self):
        def change(project, package):
            other = project["definitions"]["metamodels"][0]["packages"][0]
            other.setdefault("dataTypes", []).append(
                dict(name="Text", instanceClassName="java.math.BigDecimal"))
            other["classes"].append(dict(name="TestDerived", superTypes=[
                dict(name="Entity", package="alm", metamodel=dict(id=ALM_ID))], attributes=[
                    dict(name="locator", type=dict(name="Locator", package="alm",
                         metamodel=dict(id=ALM_ID)), lowerBound=1),
                    dict(name="localNumber", type=dict(name="Text", package=other["name"]))]))

        contracts = self.altered_contracts(change)
        key = next(k for k in contracts.classes if k[2] == "TestDerived")
        cls = contracts.classes[key]
        data = dict(id="id", version="ver", provenance="source-id", locator="any locator",
                    localNumber=Decimal("0.1234567890123456789"))
        self.assertEqual(cls.model_validate(data).model_dump(by_alias=True), data)
        schema = cls.model_json_schema(by_alias=True)["properties"]
        self.assertEqual(schema["id"]["aimpro"]["data_type"], [ALM_ID, "alm", "Identifier"])
        self.assertEqual(schema["localNumber"]["aimpro"]["data_type"], [key[0], key[1], "Text"])

    def test_unsupported_unused_and_ambiguous_declarations_are_rejected(self):
        variants = [
            lambda p, pkg: pkg["dataTypes"].append(dict(name="Unused", instanceClassName="java.lang.Object")),
            lambda p, pkg: pkg["dataTypes"][0].pop("instanceClassName"),
            lambda p, pkg: pkg["dataTypes"][0].update(instanceClassName=["java.lang.String"]),
            lambda p, pkg: pkg["dataTypes"][0].update(baseType="EString"),
            lambda p, pkg: pkg["dataTypes"].append(deepcopy(pkg["dataTypes"][0])),
            lambda p, pkg: pkg["dataTypes"].append(dict(name="Entity", instanceClassName="java.lang.String")),
            lambda p, pkg: pkg["dataTypes"].append(dict(name="EvidenceKind", instanceClassName="java.lang.String")),
        ]
        for i, change in enumerate(variants):
            with self.subTest(variant=i), self.assertRaisesRegex(ValueError, "dataType|Duplicate type"):
                self.altered_contracts(change)

    def test_decimal_lists_and_inherited_fields_keep_exact_json_values(self):
        def change(project, pkg):
            base = next(c for c in pkg["classes"] if c["name"] == "RubricLevel")
            next(a for a in base["attributes"] if a["name"] == "score").update(
                lowerBound=1, upperBound=2)
            pkg["classes"].append(dict(name="TestDecimalChild", superTypes=[
                dict(name="RubricLevel", package="alm")]))

        contracts = self.altered_contracts(change)
        cls = contracts.classes[(ALM_ID, "alm", "TestDecimalChild")]
        raw = '{"key":"k","descriptor":"d","score":[0.12345678901234567890,1e-40]}'
        value = cls.model_validate_json(raw)
        self.assertEqual(value.model_dump(by_alias=True)["score"],
                         [Decimal("0.12345678901234567890"), Decimal("1e-40")])
        for scores in ([], [1, 2, 3], [True]):
            with self.subTest(scores=scores), self.assertRaises(ValidationError):
                cls.model_validate_json(json.dumps(dict(key="k", descriptor="d", score=scores)))

    def test_unknown_scalar_types_and_nonclass_reference_targets_are_rejected(self):
        descriptors = [dict(name="Missing", package="alm"), dict(name="Entity", package="alm"),
                       dict(name="Text", package="missing"), dict(name="Text", package="alm",
                            metamodel=dict(name="alm")),
                       dict(name="Text", package="alm", metamodel=dict(id="missing")),
                       dict(name="Text", package="alm", primitive="EString"), "Text"]
        for descriptor in descriptors:
            def change(project, pkg):
                pkg["classes"][0]["attributes"][0]["type"] = descriptor
            with self.subTest(descriptor=descriptor), self.assertRaises(ValueError):
                self.altered_contracts(change)
        for target in ("Text", "EvidenceKind"):
            def change(project, pkg):
                pkg["classes"][0]["references"][0]["type"] = dict(name=target, package="alm")
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "reference target"):
                self.altered_contracts(change)

    def test_new_export_preserves_existing_schemas_and_source_values(self):
        old = Contracts()
        new_schemas = self.contracts.schemas()
        for name, schema in old.schemas().items():
            self.assertEqual(new_schemas[name], schema)
        before = NEW_PROJECT.read_bytes()
        old_closure = load_scenario().model_dump()
        new_closure = load_scenario(NEW_PROJECT).model_dump()
        for key in ("objects", "competency_ids", "excluded_scenario_object_ids", "diagnostics"):
            self.assertEqual(old_closure[key], new_closure[key])
        self.assertEqual(validate_scenario(NEW_PROJECT)["findings"], validate_scenario()["findings"])
        report = summary(NEW_PROJECT)
        self.assertEqual({r["status"] for r in report["typing"]}, {"PENDING"})
        self.assertEqual(report["scenario"], summary()["scenario"])
        audit = audit_project(NEW_PROJECT)
        self.assertEqual(len(audit["models"]), 6)
        for code in ("DUPLICATE_OWNED_ID", "UNRESOLVED_REFERENCE", "EXTERNAL_WITHOUT_OWNER",
                     "EXTERNAL_SNAPSHOT_DIFFERS", "EXTERNAL_SNAPSHOT_QUALIFIERS"):
            self.assertNotIn(code, audit["finding_counts"])
        self.assertEqual(NEW_PROJECT.read_bytes(), before)

    def test_generation_is_reproducible_and_checks_both_source_versions(self):
        self.assertTrue(generate(check=True))
        self.assertTrue(generate(NEW_PROJECT, NEW_OUTPUT, check=True))
        with TemporaryDirectory() as directory:
            target = Path(directory) / "generated"
            generate(NEW_PROJECT, target)
            self.assertTrue(generate(NEW_PROJECT, target, check=True))
            self.assertEqual({p.name: p.read_bytes() for p in target.glob("*.json")},
                             {p.name: p.read_bytes() for p in NEW_OUTPUT.glob("*.json")})
            (target / "manifest.json").write_text("{}", encoding="utf-8")
            self.assertFalse(generate(NEW_PROJECT, target, check=True))


if __name__ == "__main__":
    unittest.main()
