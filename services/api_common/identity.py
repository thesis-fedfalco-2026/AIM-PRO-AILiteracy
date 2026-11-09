"""Host-side map from an authenticated (issuer, ``sub``) to a trusted policy subject key (D9).

The map grants nothing: what a subject may do stays in the trusted policy.
Provider roles and groups are ignored. An identity that is not listed has no
subject and is refused.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator

from learning.contracts import Record, Text


class MappedIdentity(Record):
    issuer: Text
    subject: Text
    subject_key: Text


class IdentityMap(Record):
    format: Literal[1]
    identities: tuple[MappedIdentity, ...]

    @model_validator(mode='after')
    def _unique(self):
        keys = [(entry.issuer, entry.subject) for entry in self.identities]
        if len(keys) != len(set(keys)):
            raise ValueError('An identity is mapped more than once')
        return self

    def subject_key(self, issuer: str, subject: str) -> str | None:
        """Exact match on both values; no normalization of the issuer URL."""
        return next((entry.subject_key for entry in self.identities
                     if (entry.issuer, entry.subject) == (issuer, subject)), None)


def load_identity_map(path: Path) -> IdentityMap:
    return IdentityMap.model_validate_json(Path(path).read_bytes())
