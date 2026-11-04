import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator


Key = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


def resource_key(identity: str, version: str) -> str:
    return json.dumps([identity, version], ensure_ascii=False, separators=(",", ":"))


class PreparationDocumentRef(BaseModel):
    """An exact, content-pinned excerpt requested by authoring application control."""
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)
    resource_id: Key
    resource_version: Key
    document_id: Key
    content_sha256: Annotated[str, StringConstraints(strict=True, pattern=r'^[0-9a-f]{64}$')]

    @model_validator(mode='after')
    def exact_version(self):
        if self.resource_version.lower() == 'latest':
            raise ValueError('An exact resource version is required')
        return self


def preparation_selection(selections, scope):
    scope = SearchScope.model_validate(scope)
    refs = tuple(PreparationDocumentRef.model_validate(ref) for ref in selections)
    if scope.mode != 'PREPARATION' or not scope.source_scope_keys:
        raise ValueError('Exact authoring fetch requires an explicit preparation source scope')
    if not 1 <= len(refs) <= 20 or len({r.document_id for r in refs}) != len(refs):
        raise ValueError('Request between one and twenty unique excerpts')
    return refs, scope


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
