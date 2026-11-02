"""Inspect a jjodel project without repairing or executing its content."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "docs/resources/aimpro-megamodel-2026-11-02.json"


def objects(items):
    """Walk owned objects; external snapshots are indexed separately."""
    for item in items:
        yield item
        for children in item.get("children", {}).values():
            yield from objects(children)


def audit(path=DEFAULT_PROJECT, scenario="SCN01", competencies="elena_usecase_competencies"):
    raw = Path(path).read_bytes()
    project = json.loads(raw)
    if project.get("format") != "jjodel-megamodel" or project.get("formatVersion") != "1.0":
        raise ValueError("Expected jjodel-megamodel format 1.0")
    models = project["definitions"]["models"]
    selected = []
    for name in (scenario, competencies):
        matches = [m for m in models if m["metadata"]["name"] == name]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one model named {name}")
        selected.append(matches[0])
    owned = {}
    findings = []

    def finding(code, model, item, field, **detail):
        findings.append(dict(code=code, model=model, object_id=item["id"],
                             object_name=item.get("name"), field=field, **detail))

    for model in models:
        for item in objects(model.get("objects", [])):
            if item["id"] in owned:
                finding("DUPLICATE_OWNED_ID", model["metadata"]["name"], item, "id")
            owned[item["id"]] = item
    classes, enums = {}, {}
    for metamodel in project["definitions"]["metamodels"]:
        for package in metamodel["packages"]:
            for cls in package.get("classes", []):
                classes[(package["name"], cls["name"])] = cls
            for enum in package.get("enums", []):
                enums[(package["name"], enum["name"])] = {v["name"] for v in enum["literals"]}

    def descriptors(key, visiting=()):
        if key in visiting:
            raise ValueError(f"Cyclic inheritance: {key}")
        cls = classes[key]
        result = {}
        for parent in cls.get("superTypes", []):
            result.update(descriptors((parent["package"], parent["name"]), visiting + (key,)))
        for kind in ("attributes", "references"):
            result.update({field["name"]: (kind, field) for field in cls.get(kind, [])})
        return result

    summaries = []
    for model in selected:
        name = model["metadata"]["name"]
        items = list(objects(model.get("objects", [])))
        snapshots = {o["id"]: o for o in objects(model.get("externalObjects", []))}
        for oid, snapshot in snapshots.items():
            if oid not in owned:
                finding("EXTERNAL_WITHOUT_OWNER", name, snapshot, "id")
            elif any(snapshot.get(k) != owned[oid].get(k) for k in ("attributes", "references", "children")):
                finding("EXTERNAL_SNAPSHOT_DIFFERS", name, snapshot, "id")
        cross_refs = []
        local_ids = {o["id"] for o in items}
        for item in items:
            key = (item["class"]["package"], item["class"]["name"])
            if key not in classes:
                finding("UNKNOWN_CLASS", name, item, "class")
                continue
            fields = descriptors(key)
            supplied = {**item.get("attributes", {}), **item.get("references", {}), **item.get("children", {})}
            for field in supplied.keys() - fields.keys():
                finding("UNKNOWN_FIELD", name, item, field)
            for field, (kind, spec) in fields.items():
                value = supplied.get(field)
                values = [] if value is None else value if isinstance(value, list) else [value]
                lower, upper = spec.get("lowerBound", 0), spec.get("upperBound", 1)
                if len(values) < lower or (upper != -1 and len(values) > upper):
                    finding("CARDINALITY", name, item, field, count=len(values), lower=lower, upper=upper)
                if upper == 1 and isinstance(value, list) and kind == "attributes":
                    finding("SCALAR_EXPECTED", name, item, field)
                if kind == "attributes":
                    typ = spec["type"]
                    allowed = enums.get((typ["package"], typ["name"])) if isinstance(typ, dict) else None
                    for v in values:
                        if allowed is not None and (not isinstance(v, str) or v not in allowed):
                            finding("ENUM_VALUE", name, item, field, value=v, allowed=sorted(allowed))
                        if typ == "EString" and not isinstance(v, str):
                            finding("STRING_EXPECTED", name, item, field)
                else:
                    for ref in values:
                        oid = ref.get("$ref", ref.get("id")) if isinstance(ref, dict) else None
                        if oid not in owned:
                            finding("UNRESOLVED_REFERENCE", name, item, field, target=oid)
                        elif oid not in local_ids:
                            cross_refs.append(dict(source=item["id"], field=field, target=oid))
            # Compare free-text values with related external vocabularies without coercion.
            for field, enum in (("ksa", "KSA"), ("proficiency", "Proficiency")):
                if key == ("Competencies", "Competency"):
                    value = item.get("attributes", {}).get(field)
                    allowed = enums[("Competencies", enum)]
                    if value is not None and value not in allowed:
                        finding("UNTYPED_VOCABULARY_VALUE", name, item, field, value=value, allowed=sorted(allowed))
        summaries.append(dict(name=name, metamodel=model["metamodel"]["name"],
                              object_count=len(items), classes=dict(sorted(Counter(o["class"]["name"] for o in items).items())),
                              cross_model_references=cross_refs))
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(), models=summaries,
                finding_counts=dict(sorted(Counter(f["code"] for f in findings).items())), findings=findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--scenario", default="SCN01")
    parser.add_argument("--competencies", default="elena_usecase_competencies")
    args = parser.parse_args()
    print(json.dumps(audit(args.project, args.scenario, args.competencies), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
