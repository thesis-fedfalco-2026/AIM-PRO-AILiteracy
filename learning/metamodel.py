from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

from learning.contracts import Entity, EntityRef


SPEC_PATH = Path(__file__).resolve().parents[1] / "docs/resources/metamodello-agnostico-apprendimento.json"
SPEC_DIGEST = "e86b73ed0912f358947ca5f37cd1a4d816914af7187b75da2d341db42d34044d"


@dataclass(frozen=True)
class Contract:
    version: str
    digest: str
    entity_types: dict
    value_types: dict
    data: dict


def load_contract(path: Path = SPEC_PATH) -> Contract:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SPEC_DIGEST:
        raise ValueError("Unsupported or modified ALM contract")
    data = json.loads(raw)
    return Contract(data["metamodel"]["version"], digest,
                    {item["name"]: item for item in data["entityTypes"]},
                    data["valueTypes"], data)


def _fields(value: object, descriptors: list[dict], contract: Contract) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Expected ALM object")
    names = {item["name"] for item in descriptors}
    if value.keys() - names:
        raise ValueError("Unknown ALM fields")
    result = {}
    for field in descriptors:
        name, cardinality = field["name"], field["cardinality"]
        if name not in value:
            if cardinality in {"1", "1..*"}:
                raise ValueError(f"Missing ALM field: {name}")
            if cardinality == "0..*":
                result[name] = []
            continue
        item = value[name]
        if cardinality in {"0..*", "1..*"}:
            if not isinstance(item, list) or (cardinality == "1..*" and not item):
                raise ValueError(f"Invalid ALM cardinality: {name}")
            result[name] = [_value(x, field["type"], contract) for x in item]
        else:
            result[name] = _value(item, field["type"], contract)
    return result


def _value(value: object, kind: str, contract: Contract):
    if kind in contract.entity_types or kind == "EntityRef":
        ref = EntityRef.model_validate(value)
        if ref.type not in contract.entity_types or (kind != "EntityRef" and ref.type != kind):
            raise ValueError("Invalid reference type")
        if ref.version.lower() == "latest":
            raise ValueError("Reference requires an exact version")
        return ref.model_dump()
    if kind in contract.value_types:
        return _fields(value, contract.value_types[kind]["fields"], contract)
    if kind in contract.data["vocabularies"]:
        if not isinstance(value, str) or value not in contract.data["vocabularies"][kind]:
            raise ValueError(f"Invalid ALM vocabulary: {kind}")
        return value
    if kind == "Boolean":
        if type(value) is not bool:
            raise ValueError("Expected Boolean")
    elif kind == "Number":
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Expected finite Number")
    else:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Expected nonblank {kind}")
        if kind == "Version" and value.lower() == "latest":
            raise ValueError("Expected exact version")
        if kind == "Timestamp":
            try:
                timestamp = datetime.fromisoformat(value)
                if timestamp.tzinfo is None:
                    raise ValueError("Timestamp requires timezone")
            except ValueError:
                raise ValueError("Invalid Timestamp") from None
    return value


def validate_entity(value: dict, contract: Contract) -> Entity:
    if not isinstance(value, dict) or value.keys() != {"type", "id", "version", "provenance", "fields"}:
        raise ValueError("Invalid ALM entity envelope")
    kind = value["type"]
    if not isinstance(kind, str) or kind not in contract.entity_types:
        raise ValueError("Unknown ALM entity type")
    common = _fields({name: value[name] for name in ("id", "version", "provenance")},
                     contract.data["notation"]["commonEntityFields"], contract)
    fields = _fields(value["fields"], contract.entity_types[kind]["fields"], contract)
    return Entity(type=kind, fields=fields, **common)


def lead_contract(contract: Contract, roles: frozenset[str]) -> str:
    core = {name: contract.data[name] for name in contract.data["readingGuide"]["leadCore"]}
    core["workerTaxonomy"] = {**core["workerTaxonomy"], "categories": [
        {**category, "roles": [role for role in category["roles"] if role["role"] in roles]}
        for category in core["workerTaxonomy"]["categories"]
        if any(role["role"] in roles for role in category["roles"])
    ]}
    return json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
