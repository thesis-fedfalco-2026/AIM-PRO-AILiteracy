import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator


Key = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


def resource_key(identity: str, version: str) -> str:
    return json.dumps([identity, version], ensure_ascii=False, separators=(",", ":"))


class SearchScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    mode: Literal["PREPARATION", "LEARNING"]
    resource_keys: tuple[Key, ...] = ()
    source_scope_keys: tuple[Key, ...] = ()

    @model_validator(mode="after")
    def separate_modes(self):
        if (self.mode == "LEARNING" and self.source_scope_keys) or (self.mode == "PREPARATION" and self.resource_keys):
            raise ValueError("Search scope mixes preparation and learning")
        return self

    @property
    def keys(self) -> tuple[str, ...]:
        return self.resource_keys if self.mode == "LEARNING" else self.source_scope_keys

    @property
    def metadata_key(self) -> str:
        return "resource_key" if self.mode == "LEARNING" else "source_scope"

    def matches(self, metadata: dict) -> bool:
        return isinstance(metadata.get(self.metadata_key), str) and metadata[self.metadata_key] in self.keys
