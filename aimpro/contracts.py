"""Generate Pydantic domain classes from canonical, externally owned definitions.

References carry exact object ids; graph assignability is checked separately.
No exported text is evaluated as Python code.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from aimpro.audit import DEFAULT_PROJECT


Key = tuple[str, str, str]
GENERATOR_VERSION = "1"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def type_name(key: Key):
    # The digest is an identifier, not source text or an executable class name.
    return "Aimpro_" + hashlib.sha256(encoded(key).encode()).hexdigest()[:20]


class DomainObject(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False,
                              populate_by_name=False, validate_default=True)


class Contracts:
    def __init__(self, path=DEFAULT_PROJECT):
        raw = Path(path).read_bytes()
        source = json.loads(raw)
        if source.get("format") != "jjodel-megamodel" or source.get("formatVersion") != "1.0":
            raise ValueError("Expected jjodel-megamodel format 1.0")
        self.source_sha256 = hashlib.sha256(raw).hexdigest()
        self.definitions, self.enums, self.classes, self.fields = {}, {}, {}, {}
        canonical = []
        for metamodel in source["definitions"]["metamodels"]:
            mid = metamodel["metadata"]["id"]
            canonical.append(dict(id=mid, packages=metamodel["packages"]))
            for package in metamodel["packages"]:
                for kind, destination in (("classes", self.definitions), ("enums", self.enums)):
                    for entry in package.get(kind, []):
                        key = (mid, package["name"], entry["name"])
                        if key in self.definitions or key in self.enums:
                            raise ValueError(f"Duplicate type identity: {key}")
                        destination[key] = entry
        self.fingerprint = hashlib.sha256(encoded(canonical).encode()).hexdigest()
        for key in self.definitions:
            self._build(key, ())

    def resolve(self, descriptor, owner: Key) -> Key:
        return (descriptor.get("metamodel", {}).get("id", owner[0]),
                descriptor["package"], descriptor["name"])

    def is_subtype(self, actual: Key, expected: Key) -> bool:
        return actual in self.classes and expected in self.classes and issubclass(
            self.classes[actual], self.classes[expected])

    def _build(self, key, visiting):
        if key in self.classes:
            return self.classes[key]
        if key in visiting:
            raise ValueError(f"Cyclic class inheritance: {key}")
        if key not in self.definitions:
            raise ValueError(f"Unknown class: {key}")
        definition = self.definitions[key]
        parents = [self.resolve(p, key) for p in definition.get("superTypes", [])]
        bases = tuple(self._build(p, visiting + (key,)) for p in parents)
        fields = {}
        for parent in parents:
            for name, spec in self.fields[parent].items():
                if name in fields and fields[name] != spec:
                    raise ValueError(f"Conflicting inherited field: {key}.{name}")
                fields[name] = spec
        own = {}
        for kind in ("attributes", "references"):
            for descriptor in definition.get(kind, []):
                name = descriptor["name"]
                if name in own or name in fields:
                    raise ValueError(f"Duplicate or overridden field: {key}.{name}")
                # Retain the declaring type so inherited external types resolve correctly.
                own[name] = (kind, descriptor, key)
        fields.update(own)
        self.fields[key] = fields
        generated = {}
        for name, (kind, spec, owner) in own.items():
            lower, upper = spec.get("lowerBound", 0), spec.get("upperBound", 1)
            if lower < 0 or upper == 0 or upper < -1 or (upper != -1 and lower > upper):
                raise ValueError(f"Unsupported multiplicity: {key}.{name}")
            typ = spec["type"]
            metadata = {"aimpro": {"declared_by": list(owner), "kind": kind}}
            if kind == "references":
                target = self.resolve(typ, owner)
                if target not in self.definitions:
                    raise ValueError(f"Unknown reference target: {target}")
                annotation = Annotated[str, Field(min_length=1)]
                metadata["aimpro"].update(target=list(target), containment=spec.get("containment", False))
            elif isinstance(typ, dict):
                enum_key = self.resolve(typ, owner)
                if enum_key not in self.enums:
                    raise ValueError(f"Unknown attribute enum: {enum_key}")
                literals = [v["name"] for v in self.enums[enum_key]["literals"]]
                if not literals or len(literals) != len(set(literals)):
                    raise ValueError(f"Empty or duplicate enum: {enum_key}")
                annotation = Literal[tuple(literals)]
                metadata["aimpro"]["enum"] = list(enum_key)
            else:
                primitives = {"EString": str, "EInt": int, "EDouble": float,
                              "EBoolean": bool, "EDate": datetime}
                if typ not in primitives:
                    raise ValueError(f"Unsupported primitive: {typ}")
                annotation = primitives[typ]
            options = dict(alias=name, json_schema_extra=metadata)
            if upper != 1:
                annotation = list[annotation]
                options.update(min_length=lower)
                if upper != -1:
                    options["max_length"] = upper
                if lower:
                    default = Field(**options)
                else:
                    default = Field(default_factory=list, **options)
            elif lower:
                default = Field(**options)
            else:
                annotation = annotation | None
                default = Field(default=None, **options)
            # Aliases keep every external field intact, including Python keywords.
            safe_name = "f_" + hashlib.sha256(name.encode()).hexdigest()
            generated[safe_name] = (annotation, default)
        cls = create_model(type_name(key), __base__=bases or DomainObject, **generated)
        cls.model_config["json_schema_extra"] = {
            "aimpro": {"type": list(key), "abstract": definition.get("abstract", False)}}
        cls.model_rebuild(force=True)
        self.classes[key] = cls
        return cls

    def schemas(self):
        return {type_name(key): self.classes[key].model_json_schema(by_alias=True)
                for key in sorted(self.classes) if not self.definitions[key].get("abstract", False)}

    def manifest(self):
        return dict(generator_version=GENERATOR_VERSION, source_sha256=self.source_sha256,
                    metamodel_fingerprint=self.fingerprint,
                    types=[dict(identity=list(key), python_name=type_name(key),
                                abstract=self.definitions[key].get("abstract", False))
                           for key in sorted(self.classes)])
