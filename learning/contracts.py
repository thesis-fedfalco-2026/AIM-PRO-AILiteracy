from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints


Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class EntityRef(Record):
    type: Text
    id: Text
    version: Text


class Provenance(Record):
    origin: Literal["CONFIGURATION", "GENERATED_PROPOSAL", "INITIAL_CONTEXT",
                    "HUMAN_DECISION", "OBSERVED_EVENT", "UNRESOLVED_GAP"]
    sources: list[Text] = Field(default_factory=list)
    responsible: Text
    rationale: Text | None = None


class Entity(Record):
    type: Text
    id: Text
    version: Text
    provenance: Provenance
    fields: dict[str, JsonValue]

    @property
    def ref(self) -> EntityRef:
        return EntityRef(type=self.type, id=self.id, version=self.version)


class Finding(Record):
    code: Text
    target: Text
    severity: Literal["BLOCKING", "WARNING", "INFORMATION"] = "BLOCKING"
    reason: Text
    resolution: Text = "Correct the data or provide the required configuration."


def entity_data(entity: Entity) -> dict:
    return entity.model_dump(mode="json", exclude_none=True)


def make_entity(kind: str, identity: str, fields: dict, *, version: str = "1",
                origin: str = "CONFIGURATION", responsible: str = "application") -> Entity:
    return Entity(type=kind, id=identity, version=version, fields=fields,
                  provenance=Provenance(origin=origin, responsible=responsible))
