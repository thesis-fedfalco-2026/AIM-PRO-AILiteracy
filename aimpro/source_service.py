"""Persist real source preparation separately from model-backed syllabus work."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Literal

from pydantic import model_validator

from aimpro.lead import LeadInput, prepare_input
from aimpro.lead_types import Record, Text
from aimpro.source_selection import RetrievalTrace, SourcePlan, collect_sources
from aimpro.retrieval import SourceSelectionSummary
from aimpro.syllabus_coverage import validate_requirements
from aimpro.syllabus import generate
from aimpro.syllabus_state import candidates
from learning.context import LearningRequest
from learning.contracts import EntityRef
from learning.decisions import create_proposal, save_proposal
from learning.outputs import LearningResponse
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
    return LearningResponse.model_validate(value)


def _cached(service, owner, request_id, identity):
    row = service.store.db.execute('SELECT payload,result FROM requests WHERE owner=? AND id=?', (owner, request_id)).fetchone()
    if row is None:
        return None
    if json.loads(row['payload']).get('identity') != identity or row['result'] is None:
        raise StateConflict('Source request conflicts or has no confirmed result')
    return _result(json.loads(row['result']))


def _pending(service, owner, request_id, payload):
    row = service.store.db.execute('SELECT payload,result FROM requests WHERE owner=? AND id=?', (owner, request_id)).fetchone()
    if row is None or row['payload'] != payload or row['result'] is not None:
        raise StateConflict('Source request reservation changed')


def _fresh(service, context_id, subject_key, scope, root, project, source_sha256):
    context = _context(service, context_id, subject_key, scope)
    _draft(context)
    if context.snapshot.context.ref != root.ref or hashlib.sha256(Path(project).read_bytes()).hexdigest() != source_sha256:
        raise StateConflict('Source request context or source export changed')
    return context


def _failed(service, owner, request_id, identity, error):
    logging.getLogger('agent_system').warning('Selected-source authoring failed (%s)', type(error).__name__)
    result = LearningResponse(kind='FAILURE', content='Selected-source authoring did not complete; no proposal was applied.')
    try:
        service.store.finish_request(request_id, owner, result.model_dump(mode='json'))
    except StateConflict:
        return _cached(service, owner, request_id, identity)
    return result


def prepare_sources(service, context_id, subject_key, project, plan, *, request_id, search_client_factory,
                    scenario='SCN01', competencies='elena_usecase_competencies', root_id=None):
    plan = SourcePlan.model_validate(plan)
    with service.store.db:
        service.store.db.execute('BEGIN IMMEDIATE')
        context = _context(service, context_id, subject_key, plan.source_scope)
        root = context.snapshot.context
        request_id = LearningRequest(request_id=request_id, subject_key=subject_key, context_ref=root.ref,
                                     text='Prepare selected Curator sources', intent='CURATE').request_id
        data = prepare_input(project, scenario=scenario, competencies=competencies, root_id=root_id)
        if data.source.source_sha256 != plan.source_sha256:
            raise ValueError('Source plan does not identify the exact scenario export')
        validate_requirements(data, plan.coverage_requirements)
        identity = {'operation': 'AIMPRO_SOURCE_PREPARATION', 'subject_key': subject_key,
            'source_sha256': data.source.source_sha256, 'metamodel_fingerprint': data.metamodel_fingerprint,
            'root_id': data.source.root_id, 'plan': plan.model_dump(mode='json')}
        cached = _cached(service, context_id, request_id, identity)
        if cached is not None:
            return cached
        _draft(context)
        payload = canonical({'identity': identity, 'context': root.model_dump(mode='json'),
                             'source_snapshot': data.model_dump(mode='json')})
        service.store.db.execute('INSERT INTO requests VALUES (?,?,?,NULL)', (request_id, context_id, payload))
    try:
        evidence, trace = collect_sources(plan, search_client_factory())
        data = data.model_copy(update={'corpus_evidence': evidence})
        result = PreparedSources(subject_key=subject_key, context=root.ref, data=data, trace=trace)
        with service.store.db:
            service.store.db.execute('BEGIN IMMEDIATE')
            _pending(service, context_id, request_id, payload)
            _fresh(service, context_id, subject_key, plan.source_scope, root, project, plan.source_sha256)
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        return _failed(service, context_id, request_id, identity, error)


def _packet(service, owner, subject, request_id):
    row = service.store.db.execute('SELECT payload,result FROM requests WHERE owner=? AND id=?', (owner, request_id)).fetchone()
    if row is None or row['result'] is None:
        raise ValueError('A completed host source preparation is required')
    identity = json.loads(row['payload']).get('identity', {})
    if identity.get('operation') != 'AIMPRO_SOURCE_PREPARATION' or identity.get('subject_key') != subject:
        raise ValueError('Source preparation belongs to another operation or subject')
    packet = PreparedSources.model_validate_json(row['result'])
    if (packet.subject_key != subject or packet.context.id != owner or
            packet.trace.plan.model_dump(mode='json') != identity.get('plan') or
            packet.data.source.source_sha256 != identity.get('source_sha256')):
        raise ValueError('Prepared source identity differs from its reserved input')
    return packet


def generate_selected_syllabus(service, context_id, subject_key, project, *, request_id, prepared_sources,
                              source_scope, authoring_factory, scenario='SCN01',
                              competencies='elena_usecase_competencies', root_id=None):
    with service.store.db:
        service.store.db.execute('BEGIN IMMEDIATE')
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
        service.store.db.execute('INSERT INTO requests VALUES (?,?,?,NULL)', (request_id, context_id, payload))
    try:
        dispatcher, lead, budget = authoring_factory()
        draft, verdict = generate(data, dispatcher=dispatcher, lead=lead, max_context_chars=budget)
        with service.store.db:
            service.store.db.execute('BEGIN IMMEDIATE')
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
            result = LearningResponse(kind='PROPOSAL', content='Selected-source Curator syllabus awaits human review.',
                                      proposal_refs=(proposal.ref,), application_status='pending')
            save_proposal(service.store, current, proposal, saved)
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        return _failed(service, context_id, request_id, identity, error)
