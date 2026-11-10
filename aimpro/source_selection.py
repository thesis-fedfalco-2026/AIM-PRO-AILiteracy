"""Host-controlled multi-query discovery and exact excerpt selection."""

from collections import Counter
import hashlib
from typing import Literal

from pydantic import Field, StrictInt, model_validator

from aimpro.lead_types import Record, Text
from aimpro.syllabus_coverage import CoverageRequirement
from aimpro.retrieval import (CorpusEvidence, SelectedExcerpt, SourceQuery,
                             SourceSelectionSummary, evidence_from_response)
from document_search.contracts import PreparationDocumentRef, SearchScope, resource_key
from learning.store import canonical


class SourcePlan(Record):
    format: Literal['aimpro-source-plan'] = 'aimpro-source-plan'
    format_version: Literal[1] = 1
    source_sha256: Text
    source_scope: Text
    queries: tuple[SourceQuery, ...] = Field(min_length=1, max_length=20)
    documents: tuple[SelectedExcerpt, ...] = Field(min_length=1, max_length=20)
    min_resources: StrictInt = Field(default=1, ge=1, le=20)
    max_documents_per_resource: StrictInt = Field(default=4, ge=1, le=20)
    coverage_requirements: tuple[CoverageRequirement, ...] = Field(default=(), max_length=48,
                                                                  exclude_if=lambda value: not value)

    @model_validator(mode='after')
    def unique_and_diverse(self):
        if len({q.query for q in self.queries}) != len(self.queries):
            raise ValueError('Discovery queries must be unique')
        if len({r.key for r in self.coverage_requirements}) != len(self.coverage_requirements):
            raise ValueError('Coverage requirement keys must be unique')
        if len({d.document_id for d in self.documents}) != len(self.documents):
            raise ValueError('Selected document ids must be unique')
        if len({d.content_sha256 for d in self.documents}) != len(self.documents):
            raise ValueError('Repeated excerpt content is not independent evidence')
        versions = {}
        for doc in self.documents:
            if doc.resource_id in versions and versions[doc.resource_id] != doc.resource_version:
                raise ValueError('Select one exact version of each resource')
            versions[doc.resource_id] = doc.resource_version
        if len(versions) < self.min_resources or max(Counter(d.resource_id for d in self.documents).values()) > self.max_documents_per_resource:
            raise ValueError('Selected sources violate the explicit diversity limits')
        return self


class SourceDiscovery(Record):
    """The queries a teacher runs to find excerpts for a source plan; no excerpt is selected yet."""
    format: Literal['aimpro-source-discovery'] = 'aimpro-source-discovery'
    format_version: Literal[1] = 1
    source_scope: Text
    queries: tuple[SourceQuery, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode='after')
    def unique_queries(self):
        if len({q.query for q in self.queries}) != len(self.queries):
            raise ValueError('Discovery queries must be unique')
        return self


class QueryTrace(Record):
    query: SourceQuery
    evidence: CorpusEvidence


class RetrievalTrace(Record):
    format: Literal['aimpro-source-trace'] = 'aimpro-source-trace'
    format_version: Literal[1] = 1
    plan: SourcePlan
    discoveries: tuple[QueryTrace, ...]
    selected: CorpusEvidence
    unique_discovered_documents: int
    duplicate_document_hits: int

    @property
    def digest(self):
        return hashlib.sha256(canonical(self.model_dump(mode='json')).encode()).hexdigest()


def discover(queries, source_scope, client):
    """Run each query in the PREPARATION scope; the evidence per query, the unique documents and resources, the hits."""
    scope = SearchScope(mode='PREPARATION', source_scope_keys=(source_scope,))
    documents, resource_metadata, discoveries = {}, {}, []
    hits = 0
    for query in queries:
        evidence = evidence_from_response(query.query, source_scope, query.k,
                                          client.search(query.query, query.k, scope=scope))
        discoveries.append(QueryTrace(query=query, evidence=evidence))
        for resource in evidence.resources:
            metadata = resource.model_dump(mode='json', exclude={'documents'})
            if resource.key in resource_metadata and resource_metadata[resource.key] != metadata:
                raise ValueError('Resource metadata conflicts across discovery queries')
            resource_metadata[resource.key] = metadata
            for doc in resource.documents:
                hits += 1
                payload = doc.model_dump(mode='json', exclude={'score'})
                if doc.id in documents and documents[doc.id] != payload:
                    raise ValueError('Excerpt content or metadata conflicts across discovery queries')
                documents[doc.id] = payload
    return tuple(discoveries), documents, resource_metadata, hits


def collect_sources(plan, client):
    plan = SourcePlan.model_validate(plan)
    scope = SearchScope(mode='PREPARATION', source_scope_keys=(plan.source_scope,))
    discoveries, documents, resource_metadata, hits = discover(plan.queries, plan.source_scope, client)
    if any(resource_key(d.resource_id, d.resource_version) not in resource_metadata for d in plan.documents):
        raise ValueError('Every selected resource must be discovered by the recorded queries')
    refs = tuple(PreparationDocumentRef.model_validate(d.model_dump(include=set(PreparationDocumentRef.model_fields)))
                 for d in plan.documents)
    response = client.fetch_preparation_documents(refs, scope=scope)
    selected = evidence_from_response('Exact selection from recorded discovery queries', plan.source_scope,
                                     len(refs), response)
    fetched = {d.id: (r, d) for r in selected.resources for d in r.documents}
    if set(fetched) != {d.document_id for d in plan.documents}:
        raise ValueError('Exact excerpt fetch is incomplete or contains unrequested documents')
    for ref in plan.documents:
        resource, doc = fetched[ref.document_id]
        if (resource.identity != ref.resource_id or resource.version != ref.resource_version or
                doc.metadata['source'] != ref.resource_id or
                hashlib.sha256(doc.text.encode()).hexdigest() != ref.content_sha256 or
                resource.model_dump(mode='json', exclude={'documents'}) != resource_metadata[resource.key]):
            raise ValueError('Selected resource metadata, version or excerpt changed')
        if doc.id in documents and documents[doc.id] != doc.model_dump(mode='json', exclude={'score'}):
            raise ValueError('Selected excerpt differs from discovery')
    trace = RetrievalTrace(plan=plan, discoveries=tuple(discoveries), selected=selected,
                          unique_discovered_documents=len(documents), duplicate_document_hits=hits-len(documents))
    evidence = selected.model_copy(update={'selection': SourceSelectionSummary(trace_sha256=trace.digest,
        queries=plan.queries, documents=plan.documents, coverage_requirements=plan.coverage_requirements)})
    return evidence, trace
