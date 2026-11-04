"""Check whether requested AIM-PRO changes appear in a jjodel project.

The metamodel and its instances are externally owned. This module never edits
them: it reports whether an export satisfies the requests in
docs/aimpro/metamodel-change-requests.md, so #2/#3/#4 can close on evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from aimpro.adapter import load_scenario
from aimpro.audit import DEFAULT_PROJECT, audit_project, objects


# (request, package, class, attribute, proposed enum or None for a structured type)
TYPING_REQUESTS = (
    ("CR-T1", "Competencies", "Competency", "ksa", ("Competencies", "KSA")),
    ("CR-T2", "Competencies", "Competency", "proficiency", ("Competencies", "Proficiency")),
    ("CR-T3", "Certification Design", "CompetencyCluster", "primaryKSA", ("Competencies", "KSA")),
    ("CR-T4", "Certification Design", "CompetencyCluster", "proficiency", ("Competencies", "Proficiency")),
    ("CR-T5", "Resources", "Resource", "resourceType", ("Resources", "ResourceType")),
    ("CR-T6", "Users", "iSQD_Profile", "context", ("Users", "LearningContext")),
    ("CR-T7", "Scenario", "iSQD_Profile", "aiAttitude", ("Users", "Attitude")),
    ("CR-T8", "Scenario", "iSQD_Profile", "aiConfidence", ("Users", "Confidence")),
    ("CR-T9", "iSQD", "LearnerPersona", "attitude", ("Users", "Attitude")),
    ("CR-T10", "iSQD", "LearnerPersona", "confidence", ("Users", "Confidence")),
    ("CR-S1", "Certification Design", "AssessmentBlueprint", "passRules", None),
    ("CR-S2", "Activities", "RubricTask", "rubricKey", None),
    ("CR-S3", "iSQD", "LearnerPersona", "role", None),
    ("CR-S4", "Scenario", "iSQD_Profile", "role", None),
    ("CR-S5", "Users", "iSQD_Profile", "role", None),
)
EVIDENCE_TYPE = ("Certification Design", "EvidenceTypes")


def _type_key(typ):
    return (typ["package"], typ["name"]) if isinstance(typ, dict) else typ


def _definitions(project):
    classes, enums = {}, {}
    for metamodel in project["definitions"]["metamodels"]:
        for package in metamodel["packages"]:
            for cls in package.get("classes", []):
                classes[(package["name"], cls["name"])] = cls
            for enum in package.get("enums", []):
                enums[(package["name"], enum["name"])] = {v["name"] for v in enum["literals"]}
    return classes, enums


def _lineage(classes, key):
    result, pending = set(), [key]
    while pending:
        current = pending.pop()
        if current in result or current not in classes:
            continue
        result.add(current)
        pending.extend((p["package"], p["name"]) for p in classes[current].get("superTypes", []))
    return result


def _load(path):
    project = json.loads(Path(path).read_bytes())
    if project.get("format") != "jjodel-megamodel" or project.get("formatVersion") != "1.0":
        raise ValueError("Expected jjodel-megamodel format 1.0")
    return project


def typing_status(path=DEFAULT_PROJECT):
    """Report each typing request as APPLIED, PENDING, OTHER_TYPE or NOT_DECLARED.

    Blocking values are instance values that would violate the proposed enum;
    observed values of structured requests are listed for owner review only.
    """
    project = _load(path)
    classes, enums = _definitions(project)
    instances = [(m["metadata"]["name"], o) for m in project["definitions"]["models"]
                 for o in objects(m.get("objects", []))]
    report = []
    for request, package, name, attribute, proposed in TYPING_REQUESTS:
        cls = classes.get((package, name))
        spec = next((a for a in (cls or {}).get("attributes", []) if a["name"] == attribute), None)
        current = None if spec is None else _type_key(spec["type"])
        if spec is None:
            status = "NOT_DECLARED"
        elif current == "EString":
            status = "PENDING"
        elif proposed is None or current == proposed:
            status = "APPLIED"
        else:
            status = "OTHER_TYPE"
        values = []
        for model, item in instances:
            if (package, name) not in _lineage(classes, (item["class"]["package"], item["class"]["name"])):
                continue
            value = item.get("attributes", {}).get(attribute)
            for v in [] if value is None else value if isinstance(value, list) else [value]:
                if proposed is None or v not in enums.get(proposed, set()):
                    values.append(dict(model=model, object_id=item["id"],
                                       object_name=item.get("name"), value=v))
        entry = dict(request=request, attribute=f"{package}.{name}.{attribute}",
                     proposed="/".join(proposed) if proposed else "structured type",
                     current="/".join(current) if isinstance(current, tuple) else current,
                     status=status)
        entry["blocking_values" if proposed else "observed_values"] = values
        report.append(entry)
    return report


def _reachable(classes, root):
    """Classes a root can reach through references/containment, including subclasses."""
    subclasses = {}
    for key, cls in classes.items():
        for parent in cls.get("superTypes", []):
            subclasses.setdefault((parent["package"], parent["name"]), set()).add(key)
    seen, pending = set(), [root]
    while pending:
        key = pending.pop()
        if key in seen or key not in classes:
            continue
        seen.add(key)
        pending.extend(subclasses.get(key, ()))
        for ancestor in _lineage(classes, key):
            pending.extend(_type_key(r["type"]) for r in classes[ancestor].get("references", []))
    return seen


def scenario_completeness(path=DEFAULT_PROJECT, scenario="SCN01",
                          competencies="elena_usecase_competencies"):
    """Check the #2 requirements on the resolved scenario closure.

    NOT_EXPRESSIBLE means the scenario metamodel cannot hold the information,
    so it cannot be satisfied by populating the instance alone.
    """
    project = _load(path)
    classes, _ = _definitions(project)
    closure = load_scenario(path, scenario=scenario, competencies=competencies)
    reachable = _reachable(classes, ("iSQD", "Scenario"))

    def declares(key, predicate):
        return any(predicate(a) for c in _lineage(classes, key)
                   for a in classes[c].get("attributes", []))

    def requirement(key, carriers, value_field):
        if not any(declares(c, carriers) for c in reachable):
            return dict(requirement=key, status="NOT_EXPRESSIBLE")
        found = [o.id for o in closure.objects
                 if declares((o.package, o.class_name), carriers)
                 and o.attributes.get(value_field(o)) not in (None, "", [])]
        return dict(requirement=key, status="SATISFIED" if found else "MISSING", objects=found)

    activities = [o.id for o in closure.objects
                  if any(c[1] == "Activity" for c in _lineage(classes, (o.package, o.class_name)))]
    evidence_field = {}
    for c in reachable:
        for anc in _lineage(classes, c):
            for a in classes[anc].get("attributes", []):
                if _type_key(a["type"]) == EVIDENCE_TYPE:
                    evidence_field[c] = a["name"]
    return [
        dict(requirement="activities", status="SATISFIED" if activities else "MISSING",
             objects=activities),
        dict(requirement="competency_tags",
             status="SATISFIED" if closure.competency_ids else "MISSING",
             objects=closure.competency_ids),
        requirement("evidence_type", lambda a: _type_key(a["type"]) == EVIDENCE_TYPE,
                    lambda o: evidence_field.get((o.package, o.class_name))),
        requirement("rubric", lambda a: a["name"] == "rubricKey", lambda o: "rubricKey"),
        dict(requirement="source_conformance",
             status="SATISFIED" if not closure.diagnostics else "MISSING",
             findings=dict(sorted(Counter(f["code"] for f in closure.diagnostics).items()))),
    ]


def summary(path=DEFAULT_PROJECT):
    project_audit = audit_project(path)
    return dict(
        source_sha256=project_audit["source_sha256"],
        project_findings={m["name"]: dict(sorted(Counter(
            f["code"] for f in project_audit["findings"] if f["model"] == m["name"]).items()))
            for m in project_audit["models"]},
        typing=typing_status(path),
        scenario=scenario_completeness(path),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=DEFAULT_PROJECT)
    args = parser.parse_args()
    print(json.dumps(summary(args.project), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
