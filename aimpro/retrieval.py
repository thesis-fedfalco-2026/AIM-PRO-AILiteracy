"""Preserve versioned corpus evidence for authoring, without granting approval."""

import json
from typing import Any

from pydantic import Field

from aimpro.lead_types import Record, Text
from document_search.contracts import resource_key


class CorpusDocument(Record):
    id: Text
    text: Text
    metadata: dict[str, Any]
    score: float = Field(allow_inf_nan=False)


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
