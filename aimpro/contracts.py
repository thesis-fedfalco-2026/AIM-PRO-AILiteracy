"""Generate Pydantic domain classes from canonical, externally owned definitions.

References carry exact object ids; graph assignability is checked separately.
No exported text is evaluated as Python code.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, WithJsonSchema, create_model

from aimpro.audit import DEFAULT_PROJECT


Key = tuple[str, str, str]
GENERATOR_VERSION = "2"
PRIMITIVES = {"EString": str, "EInt": int, "EDouble": float,
              "EBoolean": bool, "EDate": datetime}
DECIMAL_PATTERN = r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"


def decimal_string(value, info):
    if isinstance(value, str) and re.fullmatch(DECIMAL_PATTERN, value) is None:
        raise ValueError("Expected a finite decimal string with optional exponent")
    if info.mode == "json" and type(value) in (str, int, float):
        return Decimal(str(value))
    return value


# Include exponent notation emitted by Decimal serialization in the contract.
ExactDecimal = Annotated[Decimal, BeforeValidator(decimal_string), WithJsonSchema({
    "anyOf": [{"type": "number"}, {"type": "string", "pattern": DECIMAL_PATTERN}]})]
DATA_TYPE_CLASSES = {"java.lang.String": str, "java.math.BigDecimal": ExactDecimal}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def type_name(key: Key):
    # The digest is an identifier, not source text or an executable class name.
    return "Aimpro_" + hashlib.sha256(encoded(key).encode()).hexdigest()[:20]


class DomainObject(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False,
                              populate_by_name=False, validate_default=True)
    decimal_fields: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def model_validate_json(cls, json_data, **kwargs):
        # Pydantic's JSON decoder passes fractional numbers through binary floats.
        # Preserve BigDecimal tokens as exact decimal strings before validation.
        # The generated Decimal schema accepts numbers and decimal strings; its
        # JSON serialization uses strings, never a lossy float conversion.
        if cls.decimal_fields:
            try:
                value = json.loads(json_data, parse_float=Decimal)
            except (ValueError, UnicodeDecodeError):
                return super().model_validate_json(json_data, **kwargs)
            if isinstance(value, dict):
                for name in cls.decimal_fields:
                    raw = value.get(name)
                    if isinstance(raw, Decimal):
                        value[name] = str(raw)
                    elif isinstance(raw, list):
                        value[name] = [str(v) if isinstance(v, Decimal) else v for v in raw]
                json_data = json.dumps(value, default=float)
        return super().model_validate_json(json_data, **kwargs)


class Contracts:
    def __init__(self, path=DEFAULT_PROJECT):
        raw = Path(path).read_bytes()
        source = json.loads(raw)
        if source.get("format") != "jjodel-megamodel" or source.get("formatVersion") != "1.0":
            raise ValueError("Expected jjodel-megamodel format 1.0")
        self.source_sha256 = hashlib.sha256(raw).hexdigest()
        self.definitions, self.enums, self.data_types = {}, {}, {}
        self.classes, self.fields = {}, {}
        canonical = []
        for metamodel in source["definitions"]["metamodels"]:
            mid = metamodel["metadata"]["id"]
            canonical.append(dict(id=mid, packages=metamodel["packages"]))
            for package in metamodel["packages"]:
                for kind, destination in (("classes", self.definitions), ("enums", self.enums),
                                          ("dataTypes", self.data_types)):
                    for entry in package.get(kind, []):
                        if kind == "dataTypes" and (not isinstance(entry, dict)
                                or not isinstance(entry.get("name"), str) or not entry["name"]):
                            raise ValueError(f"Invalid dataType identity in {mid}/{package['name']}")
                        key = (mid, package["name"], entry["name"])
                        if any(key in index for index in
                               (self.definitions, self.enums, self.data_types)):
                            raise ValueError(f"Duplicate type identity: {key}")
                        destination[key] = entry
        self.fingerprint = hashlib.sha256(encoded(canonical).encode()).hexdigest()
        # Validate even unused declarations; never guess a primitive from a name.
        for key, declaration in self.data_types.items():
            if (set(declaration) != {"name", "instanceClassName"}
                    or not isinstance(declaration.get("instanceClassName"), str)
                    or declaration.get("instanceClassName") not in DATA_TYPE_CLASSES):
                raise ValueError(f"Unsupported dataType declaration: {key}: {declaration}")
        for key in self.definitions:
            self._build(key, ())

    def resolve(self, descriptor, owner: Key) -> Key:
        if (not isinstance(descriptor, dict)
                or set(descriptor) - {"name", "package", "metamodel"}
                or any(not isinstance(descriptor.get(k), str) or not descriptor[k]
                       for k in ("name", "package"))):
            raise ValueError(f"Unsupported type descriptor on {owner}: {descriptor}")
        if "metamodel" in descriptor:
            metamodel = descriptor["metamodel"]
            if (not isinstance(metamodel, dict) or set(metamodel) - {"id", "name", "nsURI"}
                    or not isinstance(metamodel.get("id"), str) or not metamodel["id"]):
                raise ValueError(f"Ambiguous metamodel qualifier on {owner}: {descriptor}")
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
                attribute_key = self.resolve(typ, owner)
                if attribute_key in self.enums:
                    literals = [v["name"] for v in self.enums[attribute_key]["literals"]]
                    if not literals or len(literals) != len(set(literals)):
                        raise ValueError(f"Empty or duplicate enum: {attribute_key}")
                    annotation = Literal[tuple(literals)]
                    metadata["aimpro"]["enum"] = list(attribute_key)
                elif attribute_key in self.data_types:
                    declaration = self.data_types[attribute_key]
                    annotation = DATA_TYPE_CLASSES[declaration["instanceClassName"]]
                    metadata["aimpro"].update(data_type=list(attribute_key),
                                             instance_class_name=declaration["instanceClassName"])
                else:
                    raise ValueError(f"Unknown or non-scalar attribute type: {attribute_key}")
            else:
                if typ not in PRIMITIVES:
                    raise ValueError(f"Unsupported primitive: {typ}")
                annotation = PRIMITIVES[typ]
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
        cls.decimal_fields = tuple(name for name, (kind, spec, owner) in fields.items()
                                   if kind == "attributes" and isinstance(spec["type"], dict)
                                   and self.resolve(spec["type"], owner) in self.data_types
                                   and self.data_types[self.resolve(spec["type"], owner)][
                                       "instanceClassName"] == "java.math.BigDecimal")
        cls.model_config["json_schema_extra"] = {
            "aimpro": {"type": list(key), "abstract": definition.get("abstract", False)}}
        cls.model_rebuild(force=True)
        self.classes[key] = cls
        return cls

    def schemas(self):
        return {type_name(key): self.classes[key].model_json_schema(by_alias=True)
                for key in sorted(self.classes) if not self.definitions[key].get("abstract", False)}

    def manifest(self):
        manifest = dict(generator_version=GENERATOR_VERSION, source_sha256=self.source_sha256,
                    metamodel_fingerprint=self.fingerprint,
                    types=[dict(identity=list(key), python_name=type_name(key),
                                abstract=self.definitions[key].get("abstract", False))
                           for key in sorted(self.classes)])
        if self.data_types:
            manifest["data_types"] = [dict(identity=list(key), **self.data_types[key])
                                      for key in sorted(self.data_types)]
        return manifest
