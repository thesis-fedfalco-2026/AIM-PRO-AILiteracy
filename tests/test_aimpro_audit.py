import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aimpro.audit import DEFAULT_PROJECT, audit


class AimproAuditTest(unittest.TestCase):
    def audit_changed(self, change):
        project = json.loads(DEFAULT_PROJECT.read_bytes())
        change(project)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(project), encoding="utf-8")
            return audit(path)

    def test_real_project_resolves_nested_cross_model_competency(self):
        original = DEFAULT_PROJECT.read_bytes()
        report = audit()
        self.assertEqual(report["models"][0]["object_count"], 7)
        self.assertEqual(report["models"][1]["object_count"], 13)
        self.assertEqual(report["models"][0]["cross_model_references"], [{
            "source": "Pointer1792169221668_USER_96", "field": "competency",
            "target": "Pointer1792169354742_USER_109"}])
        self.assertNotIn("UNRESOLVED_REFERENCE", report["finding_counts"])
        self.assertTrue(any(f["field"] == "resources" and f["code"] == "CARDINALITY"
                            for f in report["findings"]))
        self.assertEqual(DEFAULT_PROJECT.read_bytes(), original)

    def test_snapshot_does_not_hide_missing_owner(self):
        def change(project):
            model = next(m for m in project["definitions"]["models"]
                         if m["metadata"]["name"] == "elena_usecase_competencies")
            model["objects"] = [o for o in model["objects"] if o["name"] != "D04"]
        report = self.audit_changed(change)
        self.assertEqual(report["finding_counts"]["UNRESOLVED_REFERENCE"], 1)
        self.assertEqual(report["finding_counts"]["EXTERNAL_WITHOUT_OWNER"], 1)

    def test_inherited_and_untyped_vocabularies_are_checked(self):
        report = audit()
        findings = {(f["object_name"], f["field"], f["code"]) for f in report["findings"]}
        self.assertIn(("D04", "category", "ENUM_VALUE"), findings)
        self.assertIn(("D04", "proficiency", "UNTYPED_VOCABULARY_VALUE"), findings)
        def change(project):
            model = next(m for m in project["definitions"]["models"]
                         if m["metadata"]["name"] == "elena_usecase_competencies")
            model["objects"][0]["attributes"]["title"] = 42
        report = self.audit_changed(change)
        self.assertTrue(any(f["field"] == "title" and f["code"] == "STRING_EXPECTED"
                            for f in report["findings"]))

    def test_rejects_unknown_model_and_format(self):
        with self.assertRaises(ValueError):
            audit(scenario="SCN 01")
        with self.assertRaises(ValueError):
            self.audit_changed(lambda p: p.update(format="jjodel-model"))

    def test_recorded_report_is_reproducible(self):
        path = DEFAULT_PROJECT.parents[1] / "aimpro/scn01-audit.json"
        self.assertEqual(audit(), json.loads(path.read_text()))
