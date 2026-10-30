import json
from pathlib import Path

from learning.contracts import make_entity, entity_data
from learning.metamodel import load_contract, validate_entity


def ref(kind, identity, version="1"):
    return {"type": kind, "id": identity, "version": version}


def record(kind, identity, fields, version="1"):
    return validate_entity(entity_data(make_entity(kind, identity, fields, version=version)), load_contract())


def load_bundle(name="minimal"):
    path = Path(__file__).parent / "fixtures/alm" / f"{name}.json"
    return tuple(validate_entity(item, load_contract()) for item in json.loads(path.read_text()))
