"""Preserve versioned corpus evidence for authoring, without granting approval."""

import json
from typing import Annotated, Any

from pydantic import Field, StrictInt, StringConstraints, field_validator

from aimpro.lead_types import Record, Text
from aimpro.syllabus_coverage import CoverageRequirement
from document_search.contracts import PreparationDocumentRef, resource_key


class SourceQuery(Record):
    query: Text
    k: StrictInt = Field(default=20, ge=1, le=20)


class SelectedExcerpt(PreparationDocumentRef):
    purpose: Text
    limitations: tuple[Text, ...] = Field(min_length=1)


class SourceSelectionSummary(Record):
    trace_sha256: Text
    queries: tuple[SourceQuery, ...]
    documents: tuple[SelectedExcerpt, ...]
    # Omit absent extensions to preserve hashes of historical source packets.
    coverage_requirements: tuple[CoverageRequirement, ...] = Field(default=(), exclude_if=lambda value: not value)


class CorpusDocument(Record):
    id: Text
    # Exact fetched bytes determine the selection hash. Do not strip whitespace.
    text: Annotated[str, StringConstraints(strict=True, min_length=1)]
    metadata: dict[str, Any]
    score: float = Field(allow_inf_nan=False)

    @field_validator('text')
    @classmethod
    def meaningful_excerpt(cls, value):
        if not value.strip():
            raise ValueError('Excerpt text must not be blank')
        return value


class CorpusResource(Record):
    identity: Text
    version: Text
    title: Text
    uri: Text
    licence: Text
    source_scope: Text
    documents: tuple[CorpusDocument, ...] = Field(min_length=1)

    @property
    def key(self):
        return resource_key(self.identity, self.version)


class CorpusEvidence(Record):
    query: Text
    source_scope: Text
    k: int = Field(ge=1, le=20)
    resources: tuple[CorpusResource, ...]
    selection: SourceSelectionSummary | None = None


def evidence_from_response(query, source_scope, k, response):
    if response.get('truncated', False):
        raise ValueError('Grounding requires an untruncated retrieval response')
    documents = tuple(CorpusDocument.model_validate(d) for d in response['documents'])
    if len(documents) > k or len({d.id for d in documents}) != len(documents):
        raise ValueError('Retrieval returned too many or duplicate documents')
    grouped = {}
    for doc in documents:
        metadata = doc.metadata
        if metadata.get('source_scope') != source_scope:
            raise ValueError('Retrieved document is outside the authorized scope')
        raw = metadata.get('resource_key')
        parsed = json.loads(raw) if isinstance(raw, str) else None
        if (not isinstance(parsed, list) or len(parsed) != 2 or
                any(not isinstance(v, str) or not v.strip() or v != v.strip() or v.lower() == 'latest' for v in parsed)):
            raise ValueError('Retrieval requires exact resource identity and version')
        key = resource_key(*parsed)
        attrs = {name: metadata.get(name) for name in ('title', 'uri', 'licence', 'source_scope')}
        if any(not isinstance(v, str) or not v.strip() for v in attrs.values()):
            raise ValueError('Retrieval requires complete resource metadata')
        if key in grouped and grouped[key][0] != attrs:
            raise ValueError('Conflicting metadata for a resource version')
        grouped.setdefault(key, (attrs, []))[1].append(doc)
    resources = []
    for key, (attrs, docs) in grouped.items():
        identity, version = json.loads(key)
        resources.append(CorpusResource(identity=identity, version=version, documents=tuple(docs), **attrs))
    return CorpusEvidence(query=query, source_scope=source_scope, k=k, resources=tuple(resources))
