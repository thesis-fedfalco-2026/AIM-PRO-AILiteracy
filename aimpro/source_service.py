"""Persist real source preparation separately from model-backed syllabus work."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import model_validator

from aimpro.lead import LeadInput, ReviewError, prepare_input
from aimpro.lead_types import Record, Text
from aimpro.source_selection import QueryTrace, RetrievalTrace, SourceDiscovery, SourcePlan, collect_sources, discover
from aimpro.retrieval import SourceSelectionSummary
from aimpro.syllabus_coverage import validate_requirements
from aimpro.syllabus import generate
from aimpro.syllabus_state import SyllabusResult, candidates
from learning.context import LearningRequest
from learning.contracts import EntityRef
from learning.decisions import create_proposal, save_proposal
from learning.policies import scope_allows
from learning.projects import _authorize, _draft
from learning.store import StateConflict, canonical


class PreparedSources(Record):
    kind: Literal['SOURCE_PREPARATION'] = 'SOURCE_PREPARATION'
    subject_key: Text
    context: EntityRef
    data: LeadInput
    trace: RetrievalTrace

    @model_validator(mode='after')
    def exact_selected_input(self):
        expected = self.trace.selected.model_copy(update={'selection': SourceSelectionSummary(
            trace_sha256=self.trace.digest, queries=self.trace.plan.queries, documents=self.trace.plan.documents,
            coverage_requirements=self.trace.plan.coverage_requirements)})
        validate_requirements(self.data, self.trace.plan.coverage_requirements)
        if (self.context.type != 'ExecutionContext' or self.context.version.lower() == 'latest' or
                self.data.source.source_sha256 != self.trace.plan.source_sha256 or self.data.corpus_evidence != expected):
            raise ValueError('Prepared model input differs from its exact retrieval trace')
        return self

    @property
    def digest(self):
        return hashlib.sha256(canonical(self.model_dump(mode='json')).encode()).hexdigest()


class DiscoveredSources(Record):
    """What the queries of a discovery found: the teacher picks the excerpts of a source plan from it."""
    kind: Literal['SOURCE_DISCOVERY'] = 'SOURCE_DISCOVERY'
    subject_key: Text
    context: EntityRef
    discovery: SourceDiscovery
    discoveries: tuple[QueryTrace, ...]
    unique_discovered_documents: int
    duplicate_document_hits: int


OPERATIONS = {'SOURCE_DISCOVERY': 'AIMPRO_SOURCE_DISCOVERY', 'SOURCE_PREPARATION': 'AIMPRO_SOURCE_PREPARATION'}


def _context(service, context_id, subject_key, source_scope):
    context = service._context(context_id, subject_key)
    _authorize(context)
    if (not scope_allows(service.policy, source_scope, context_id, subject_key) or
            source_scope not in service.policy.scopes[source_scope].sources):
        raise ValueError('Syllabus source scope is not authorized')
    return context


def _result(value):
    if value.get('kind') == 'SOURCE_PREPARATION':
        return PreparedSources.model_validate(value)
    if value.get('kind') == 'SOURCE_DISCOVERY':
        return DiscoveredSources.model_validate(value)
    return SyllabusResult.model_validate(value)


def _cached(service, owner, request_id, identity):
    row = service.store.request_record(request_id, owner)
    if row is None:
        return None
    if json.loads(row.payload).get('identity') != identity or row.result is None:
        raise StateConflict('Source request conflicts or has no confirmed result')
    return _result(json.loads(row.result))


def _pending(service, owner, request_id, payload):
    row = service.store.request_record(request_id, owner)
    if row is None or row.payload != payload or row.result is not None:
        raise StateConflict('Source request reservation changed')


def _fresh(service, context_id, subject_key, scope, root, project, source_sha256):
    context = _context(service, context_id, subject_key, scope)
    _draft(context)
    if context.snapshot.context.ref != root.ref or hashlib.sha256(Path(project).read_bytes()).hexdigest() != source_sha256:
        raise StateConflict('Source request context or source export changed')
    return context


def _failed(service, owner, request_id, identity, error, *, operation='Selected-source authoring',
            content='Selected-source authoring did not complete{reason}; no proposal was applied.', attempts=()):
    """Record the failure; ``content`` names ``{reason}``, the fixed text of a ``ReviewError``, never model text."""
    reason = f' ({error})' if isinstance(error, ReviewError) else ''
    logging.getLogger('agent_system').warning('%s failed (%s)%s', operation, type(error).__name__, reason)
    result = SyllabusResult(kind='FAILURE', content=content.format(reason=reason),
                            attempts=getattr(error, 'attempts', attempts))
    try:
        service.store.finish_request(request_id, owner, result.model_dump(mode='json'))
    except StateConflict:
        return _cached(service, owner, request_id, identity)
    return result


def discover_sources(service, context_id, subject_key, discovery, *, request_id, search_client_factory):
    """Run the teacher's queries and record every excerpt found; no model, no entity, no proposal."""
    discovery = SourceDiscovery.model_validate(discovery)
    with service.store.write_transaction():
        context = _context(service, context_id, subject_key, discovery.source_scope)
        root = context.snapshot.context
        request_id = LearningRequest(request_id=request_id, subject_key=subject_key, context_ref=root.ref,
                                     text='Discover Curator sources', intent='CURATE').request_id
        identity = {'operation': OPERATIONS['SOURCE_DISCOVERY'], 'subject_key': subject_key,
                    'discovery': discovery.model_dump(mode='json')}
        cached = _cached(service, context_id, request_id, identity)
        if cached is not None:
            return cached
        _draft(context)
        payload = canonical({'identity': identity, 'context': root.model_dump(mode='json')})
        service.store.reserve_request(request_id, context_id, payload)
    try:
        discoveries, documents, _, hits = discover(discovery.queries, discovery.source_scope, search_client_factory())
        result = DiscoveredSources(subject_key=subject_key, context=root.ref, discovery=discovery,
                                   discoveries=discoveries, unique_discovered_documents=len(documents),
                                   duplicate_document_hits=hits - len(documents))
        with service.store.write_transaction():
            _pending(service, context_id, request_id, payload)
            current = _context(service, context_id, subject_key, discovery.source_scope)
            _draft(current)
            if current.snapshot.context.ref != root.ref:
                raise StateConflict('Source request context changed')
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        return _failed(service, context_id, request_id, identity, error, operation='Source discovery',
                       content='Source discovery did not complete{reason}; nothing was recorded for the course.')


def source_request(service, context_id, subject_key, request_id, kind):
    """The subject's completed discovery or preparation of this kind in the context; ``None`` otherwise."""
    with service.store.read_transaction():
        _authorize(service._context(context_id, subject_key))
        row = service.store.request_record(request_id, context_id)
    if row is None or row.result is None:
        return None
    identity = json.loads(row.payload).get('identity', {})
    result = json.loads(row.result)
    if (identity.get('operation') != OPERATIONS[kind] or identity.get('subject_key') != subject_key or
            result.get('kind') != kind):
        return None
    return _result(result)


def prepare_sources(service, context_id, subject_key, project, plan, *, request_id, search_client_factory,
                    scenario='SCN01', competencies='elena_usecase_competencies', root_id=None):
    plan = SourcePlan.model_validate(plan)
    with service.store.write_transaction():
        context = _context(service, context_id, subject_key, plan.source_scope)
        root = context.snapshot.context
        request_id = LearningRequest(request_id=request_id, subject_key=subject_key, context_ref=root.ref,
                                     text='Prepare selected Curator sources', intent='CURATE').request_id
        data = prepare_input(project, scenario=scenario, competencies=competencies, root_id=root_id)
        if data.source.source_sha256 != plan.source_sha256:
            raise ValueError('Source plan does not identify the exact scenario export')
        validate_requirements(data, plan.coverage_requirements)
        identity = {'operation': OPERATIONS['SOURCE_PREPARATION'], 'subject_key': subject_key,
            'source_sha256': data.source.source_sha256, 'metamodel_fingerprint': data.metamodel_fingerprint,
            'root_id': data.source.root_id, 'plan': plan.model_dump(mode='json')}
        cached = _cached(service, context_id, request_id, identity)
        if cached is not None:
            return cached
        _draft(context)
        payload = canonical({'identity': identity, 'context': root.model_dump(mode='json'),
                             'source_snapshot': data.model_dump(mode='json')})
        service.store.reserve_request(request_id, context_id, payload)
    try:
        evidence, trace = collect_sources(plan, search_client_factory())
        data = data.model_copy(update={'corpus_evidence': evidence})
        result = PreparedSources(subject_key=subject_key, context=root.ref, data=data, trace=trace)
        with service.store.write_transaction():
            _pending(service, context_id, request_id, payload)
            _fresh(service, context_id, subject_key, plan.source_scope, root, project, plan.source_sha256)
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        return _failed(service, context_id, request_id, identity, error)


def _packet(service, owner, subject, request_id):
    row = service.store.request_record(request_id, owner)
    if row is None or row.result is None:
        raise ValueError('A completed host source preparation is required')
    identity = json.loads(row.payload).get('identity', {})
    if identity.get('operation') != 'AIMPRO_SOURCE_PREPARATION' or identity.get('subject_key') != subject:
        raise ValueError('Source preparation belongs to another operation or subject')
    packet = PreparedSources.model_validate_json(row.result)
    if (packet.subject_key != subject or packet.context.id != owner or
            packet.trace.plan.model_dump(mode='json') != identity.get('plan') or
            packet.data.source.source_sha256 != identity.get('source_sha256')):
        raise ValueError('Prepared source identity differs from its reserved input')
    return packet


def generate_selected_syllabus(service, context_id, subject_key, project, *, request_id, prepared_sources,
                              source_scope, authoring_factory, scenario='SCN01',
                              competencies='elena_usecase_competencies', root_id=None):
    with service.store.write_transaction():
        context = _context(service, context_id, subject_key, source_scope)
        root = context.snapshot.context
        request_id = LearningRequest(request_id=request_id, subject_key=subject_key, context_ref=root.ref,
            text='Generate a syllabus from prepared exact sources', intent='CURATE').request_id
        data = prepare_input(project, scenario=scenario, competencies=competencies, root_id=root_id)
        identity = {'operation': 'AIMPRO_SELECTED_SYLLABUS', 'subject_key': subject_key,
            'source_sha256': data.source.source_sha256, 'metamodel_fingerprint': data.metamodel_fingerprint,
            'root_id': data.source.root_id, 'source_scope': source_scope, 'prepared_sources': prepared_sources}
        cached = _cached(service, context_id, request_id, identity)
        if cached is not None:
            return cached
        _draft(context)
        packet = _packet(service, context_id, subject_key, prepared_sources)
        if (packet.context != root.ref or packet.trace.plan.source_scope != source_scope or
                packet.data.source != data.source or packet.data.metamodel_fingerprint != data.metamodel_fingerprint):
            raise StateConflict('Prepared sources are stale, foreign or belong to a different source')
        data = packet.data
        payload = canonical({'identity': identity, 'context': root.model_dump(mode='json'),
            'preparation_sha256': packet.digest, 'model_input': data.model_dump(mode='json')})
        service.store.reserve_request(request_id, context_id, payload)
    attempts = ()
    try:
        dispatcher, lead, budget = authoring_factory()
        draft, verdict, attempts = generate(data, dispatcher=dispatcher, lead=lead, max_context_chars=budget)
        with service.store.write_transaction():
            _pending(service, context_id, request_id, payload)
            current = _fresh(service, context_id, subject_key, source_scope, root, project, data.source.source_sha256)
            if _packet(service, context_id, subject_key, prepared_sources).digest != packet.digest:
                raise StateConflict('Prepared sources changed during generation')
            saved = candidates(data, draft, verdict, current, retrieval_trace=packet.trace)
            proposal = create_proposal(current, (root.ref,), saved,
                'Review a Curator syllabus from exact selected source excerpts; no approval or learner progress is inferred. ' +
                canonical({'source_preparation': prepared_sources, 'preparation_sha256': packet.digest,
                    'retrieval_trace_sha256': packet.trace.digest, 'source_diagnostics': data.source.diagnostics,
                    'contract_findings': data.findings, 'syllabus_gaps': draft.gaps}))
            result = SyllabusResult(kind='PROPOSAL', content='Selected-source Curator syllabus awaits human review.',
                                    proposal_refs=(proposal.ref,), application_status='pending', attempts=attempts)
            save_proposal(service.store, current, proposal, saved)
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        return _failed(service, context_id, request_id, identity, error, attempts=attempts)
