"""Module ``sources``: what a source discovery found and what a source preparation holds (S09a2, D22).

The worker records both in the host requests store (jobs
``discover-aimpro-syllabus-sources`` and ``prepare-aimpro-syllabus-sources``);
these routes read them back for the teacher who ran them. A discovery lists the
excerpts its queries found, from which the teacher picks the excerpts of a
source plan; a preparation lists the exact excerpts, with the purpose and the
limitations the teacher wrote, before the teacher accepts or declines them.
Each excerpt carries its licence and the corpus licence verdict: the usage
conditions the teacher reviews. Nothing here is a proposal or an approval.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Request
from starlette.exceptions import HTTPException

from aimpro.retrieval import CorpusDocument, CorpusResource, SourceQuery
from aimpro.syllabus_coverage import CoverageRequirement
from learning.contracts import Record, Text
from services.api_common.auth import Principal
from services.api_common.contexts import READ_ERRORS, context_reader, open_context
from services.api_common.registry import ApiModule


class Excerpt(Record):
    """An exact excerpt of a corpus resource version, with the usage conditions the corpus records for it."""
    resource_id: Text
    resource_version: Text
    document_id: Text
    content_sha256: Text
    title: Text
    uri: Text
    licence: Text
    licence_verdict: Text | None
    # The exact text, whitespace included: its SHA-256 pins it in a source plan.
    text: str


class DiscoveredExcerpt(Excerpt):
    found_by: tuple[str, ...]


class PreparedExcerpt(Excerpt):
    purpose: Text
    limitations: tuple[Text, ...]


class SourceDiscoveryView(Record):
    """The excerpts the discovery queries found, each once, in the order they were found."""
    request_id: Text
    source_scope: Text
    queries: tuple[SourceQuery, ...]
    excerpts: tuple[DiscoveredExcerpt, ...]
    unique_documents: int
    duplicate_hits: int


class SourcePreparationView(Record):
    """The exact excerpts of a preparation, for the teacher's choice, and the plan they were prepared from."""
    request_id: Text
    source_scope: Text
    source_sha256: Text
    queries: tuple[SourceQuery, ...]
    excerpts: tuple[PreparedExcerpt, ...]
    coverage_requirements: tuple[CoverageRequirement, ...]
    min_resources: int
    max_documents_per_resource: int
    unique_documents: int
    duplicate_hits: int


def _excerpt(resource: CorpusResource, document: CorpusDocument) -> dict:
    verdict = document.metadata.get('licence_verdict')
    return {'resource_id': resource.identity, 'resource_version': resource.version, 'document_id': document.id,
            'content_sha256': hashlib.sha256(document.text.encode()).hexdigest(), 'title': resource.title,
            'uri': resource.uri, 'licence': resource.licence,
            'licence_verdict': verdict if isinstance(verdict, str) and verdict.strip() else None,
            'text': document.text}


def discovery_view(request_id: str, found) -> SourceDiscoveryView:
    excerpts = {}
    for trace in found.discoveries:
        for resource in trace.evidence.resources:
            for document in resource.documents:
                excerpt = excerpts.setdefault(document.id, {**_excerpt(resource, document), 'found_by': []})
                if trace.query.query not in excerpt['found_by']:
                    excerpt['found_by'].append(trace.query.query)
    return SourceDiscoveryView(request_id=request_id, source_scope=found.discovery.source_scope,
                               queries=found.discovery.queries,
                               excerpts=tuple(DiscoveredExcerpt.model_validate(e) for e in excerpts.values()),
                               unique_documents=found.unique_discovered_documents,
                               duplicate_hits=found.duplicate_document_hits)


def preparation_view(request_id: str, prepared) -> SourcePreparationView:
    plan = prepared.trace.plan
    fetched = {d.id: (r, d) for r in prepared.data.corpus_evidence.resources for d in r.documents}
    excerpts = tuple(PreparedExcerpt.model_validate({**_excerpt(*fetched[ref.document_id]), 'purpose': ref.purpose,
                                                     'limitations': ref.limitations})
                     for ref in plan.documents)
    return SourcePreparationView(request_id=request_id, source_scope=plan.source_scope,
                                 source_sha256=plan.source_sha256, queries=plan.queries, excerpts=excerpts,
                                 coverage_requirements=plan.coverage_requirements,
                                 min_resources=plan.min_resources,
                                 max_documents_per_resource=plan.max_documents_per_resource,
                                 unique_documents=prepared.trace.unique_discovered_documents,
                                 duplicate_hits=prepared.trace.duplicate_document_hits)


def _record(request: Request, context_id: str, request_id: str, subject_key: str, kind: str):
    with open_context(request, context_id) as service:
        service.authorize_jobs(context_id, subject_key)
        record = service.aimpro_source_request(context_id, subject_key, request_id, kind)
    if record is None:
        raise HTTPException(404, 'No completed source request of this kind under this id')
    return record


router = APIRouter(tags=['sources'])


@router.get('/contexts/{context_id}/source-discoveries/{request_id}', response_model=SourceDiscoveryView,
            responses=READ_ERRORS, summary='The excerpts a discovery job found, to pick a source plan from')
def discovery(context_id: str, request_id: str, request: Request, principal: Principal = Depends(context_reader)):
    found = _record(request, context_id, request_id, principal.subject_key, 'SOURCE_DISCOVERY')
    return discovery_view(request_id, found)


@router.get('/contexts/{context_id}/source-preparations/{request_id}', response_model=SourcePreparationView,
            responses=READ_ERRORS, summary="The exact excerpts of a preparation job, for the teacher's choice")
def preparation(context_id: str, request_id: str, request: Request, principal: Principal = Depends(context_reader)):
    prepared = _record(request, context_id, request_id, principal.subject_key, 'SOURCE_PREPARATION')
    return preparation_view(request_id, prepared)


MODULE = ApiModule('sources', router)
