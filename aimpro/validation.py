"""Validate an adapter projection against generated source contracts."""

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from aimpro.adapter import load_scenario
from aimpro.audit import DEFAULT_PROJECT
from aimpro.contracts import Contracts, encoded


def validate_scenario(path=DEFAULT_PROJECT, *, scenario="SCN01",
                      competencies="elena_usecase_competencies", root_id=None):
    source = load_scenario(path, scenario=scenario, competencies=competencies, root_id=root_id)
    contracts = Contracts(path)
    if source.source_sha256 != contracts.source_sha256:
        raise ValueError("Project changed during contract validation")
    index = {o.id: o for o in source.objects}
    findings, projections, conversions = [], [], []
    for item in source.objects:
        key = (item.metamodel_id, item.package, item.class_name)
        if key not in contracts.classes:
            findings.append(dict(code="UNKNOWN_CLASS", object_id=item.id, type=list(key)))
            continue
        if contracts.definitions[key].get("abstract", False):
            findings.append(dict(code="ABSTRACT_INSTANCE", object_id=item.id))
        fields = contracts.fields[key]
        value = dict(item.attributes)
        for field, raw in item.attributes.items():
            spec = fields.get(field)
            if spec and spec[0] != "attributes":
                findings.append(dict(code="FIELD_SECTION", object_id=item.id, field=field))
            if spec and spec[0] == "attributes" and spec[1].get("upperBound", 1) != 1 and not isinstance(raw, list):
                value[field] = [raw]
                conversions.append(dict(object_id=item.id, field=field, operation="SCALAR_TO_SINGLETON_LIST"))
        for section, links in (("references", item.references), ("children", item.children)):
            for field, targets in links.items():
                spec = fields.get(field)
                if spec is None or spec[0] != "references":
                    findings.append(dict(code="UNKNOWN_REFERENCE_FIELD", object_id=item.id, field=field))
                    continue
                descriptor, owner = spec[1:]
                containment = descriptor.get("containment", False)
                if containment != (section == "children"):
                    findings.append(dict(code="CONTAINMENT_SECTION", object_id=item.id, field=field))
                if field in value:
                    findings.append(dict(code="FIELD_SECTION", object_id=item.id, field=field))
                if descriptor.get("upperBound", 1) == 1:
                    if len(targets) > 1:
                        findings.append(dict(code="REFERENCE_CARDINALITY", object_id=item.id, field=field))
                    value[field] = targets[0] if targets else None
                else:
                    value[field] = targets
                expected = contracts.resolve(descriptor["type"], owner)
                for target in targets:
                    other = index.get(target)
                    actual = (other.metamodel_id, other.package, other.class_name) if other else None
                    if actual is None or not contracts.is_subtype(actual, expected):
                        findings.append(dict(code="REFERENCE_TYPE", object_id=item.id, field=field,
                                             target=target, expected=list(expected)))
        try:
            validated = contracts.classes[key].model_validate_json(encoded(value))
            projections.append(dict(object_id=item.id, type=list(key),
                                    fields=validated.model_dump(mode="json", by_alias=True)))
        except ValidationError as error:
            for finding in error.errors(include_url=False, include_input=False, include_context=False):
                findings.append(dict(code="GENERATED_CONTRACT", object_id=item.id,
                                     location=list(finding["loc"]), error=finding["type"],
                                     message=finding["msg"]))
    return dict(source=source.model_dump(mode="json"),
                metamodel_fingerprint=contracts.fingerprint,
                conforms_to_generated_contracts=not findings,
                findings=findings, transport_conversions=conversions,
                validated_objects=projections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--scenario", default="SCN01")
    parser.add_argument("--competencies", default="elena_usecase_competencies")
    parser.add_argument("--root-id")
    parser.add_argument("--require-conformance", action="store_true")
    args = parser.parse_args()
    report = validate_scenario(args.project, scenario=args.scenario,
                               competencies=args.competencies, root_id=args.root_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_conformance and not report["conforms_to_generated_contracts"]:
        parser.exit(1)


if __name__ == "__main__":
    main()
