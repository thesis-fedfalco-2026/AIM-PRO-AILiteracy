import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from aimpro.audit import DEFAULT_PROJECT
from aimpro.change_requests import (
    _definitions, _reachable, scenario_completeness, summary, typing_status)


def model(project, name):
    return next(m for m in project["definitions"]["models"] if m["metadata"]["name"] == name)


def cls(project, package, name):
    return next(c for mm in project["definitions"]["metamodels"] for p in mm["packages"]
                if p["name"] == package for c in p.get("classes", []) if c["name"] == name)


def by_request(report):
    return {entry["request"]: entry for entry in report}


class AimproChangeRequestsTest(unittest.TestCase):
    def changed(self, change, check):
        project = json.loads(DEFAULT_PROJECT.read_bytes())
        change(project)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            path.write_text(json.dumps(project), encoding="utf-8")
            return check(path)

    def test_current_export_has_every_request_pending_with_blocking_values(self):
        report = by_request(typing_status())
        self.assertEqual({e["status"] for e in report.values()}, {"PENDING"})
        self.assertEqual([v["value"] for v in report["CR-T1"]["blocking_values"]], ["SKILL"])
        self.assertEqual([v["value"] for v in report["CR-T2"]["blocking_values"]], ["FOUNDATION"])
        self.assertEqual(sorted(v["value"] for v in report["CR-T8"]["blocking_values"]),
                         ["Low", "Low", "Medium"])
        self.assertEqual([v["value"] for v in report["CR-T10"]["blocking_values"]], ["1,0"])
        self.assertEqual(report["CR-T5"]["blocking_values"], [])
        self.assertIn("HR Director", [v["value"] for v in report["CR-S4"]["observed_values"]])

    def test_applied_requests_are_recognised_without_rewriting_the_source(self):
        before = DEFAULT_PROJECT.read_bytes()

        def change(project):
            competency = cls(project, "Competencies", "Competency")
            ksa = next(a for a in competency["attributes"] if a["name"] == "ksa")
            ksa["type"] = {"name": "KSA", "package": "Competencies"}
            d04 = next(o for o in model(project, "elena_usecase_competencies")["objects"]
                       if o["name"] == "D04")
            d04["attributes"]["ksa"] = "Skill"
            blueprint = cls(project, "Certification Design", "AssessmentBlueprint")
            next(a for a in blueprint["attributes"] if a["name"] == "passRules")["type"] = "EInt"
            rubric = cls(project, "Activities", "RubricTask")
            rubric["attributes"] = [a for a in rubric["attributes"] if a["name"] != "rubricKey"]
            proficiency = next(a for a in competency["attributes"] if a["name"] == "proficiency")
            proficiency["type"] = {"name": "Relevance", "package": "Competencies"}

        report = by_request(self.changed(change, typing_status))
        self.assertEqual(report["CR-T1"]["status"], "APPLIED")
        self.assertEqual(report["CR-T1"]["blocking_values"], [])
        self.assertEqual(report["CR-S1"]["status"], "APPLIED")
        self.assertEqual(report["CR-S2"]["status"], "NOT_DECLARED")
        self.assertEqual(report["CR-T2"]["status"], "OTHER_TYPE")
        self.assertEqual(DEFAULT_PROJECT.read_bytes(), before)

    def test_isqd_scenario_cannot_express_evidence_or_rubrics(self):
        report = {e["requirement"]: e for e in scenario_completeness()}
        self.assertEqual(report["activities"]["status"], "SATISFIED")
        self.assertEqual(report["competency_tags"]["status"], "SATISFIED")
        self.assertEqual(report["evidence_type"]["status"], "NOT_EXPRESSIBLE")
        self.assertEqual(report["rubric"]["status"], "NOT_EXPRESSIBLE")
        self.assertEqual(report["source_conformance"]["status"], "MISSING")
        # The separate Scenario metamodel reaches both through its activities.
        classes, _ = _definitions(json.loads(DEFAULT_PROJECT.read_bytes()))
        reachable = _reachable(classes, ("Scenario", "Scenario"))
        self.assertIn(("Activities", "RubricTask"), reachable)
        self.assertIn(("Activities", "CaseItem"), reachable)

    def test_evidence_becomes_expressible_and_missing_when_isqd_links_activities(self):
        def change(project):
            target = cls(project, "iSQD", "LearningTarget")
            target["references"].append({
                "name": "assessmentItems", "type": {"name": "Activity", "package": "Activities"},
                "lowerBound": 0, "upperBound": -1, "containment": False})

        report = {e["requirement"]: e for e in self.changed(change, scenario_completeness)}
        self.assertEqual(report["evidence_type"]["status"], "MISSING")
        self.assertEqual(report["rubric"]["status"], "MISSING")

    def test_fixing_d04_vocabulary_leaves_only_missing_resources(self):
        def change(project):
            d04 = next(o for o in model(project, "elena_usecase_competencies")["objects"]
                       if o["name"] == "D04")
            d04["attributes"].update(category="Digital", ksa="Skill", proficiency="Foundational",
                                     heRelevance="High", smeRelevance="High", vetRelevance="High")
            snapshot = next(o for o in model(project, "SCN01")["externalObjects"]
                            if o["id"] == d04["id"])
            snapshot["attributes"] = d04["attributes"]

        report = {e["requirement"]: e for e in self.changed(change, scenario_completeness)}
        self.assertEqual(report["source_conformance"]["findings"], {"CARDINALITY": 1})

    def test_summary_covers_every_model(self):
        report = summary()
        self.assertEqual(set(report["project_findings"]), {
            "learningphase", "assessment", "elena_usecase_competencies",
            "elena_usecase_scenario", "sustainability", "SCN01"})
        self.assertEqual(len(report["typing"]), 15)


if __name__ == "__main__":
    unittest.main()
