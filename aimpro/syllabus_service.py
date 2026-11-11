"""Authorized, replayable syllabus generation in the local proposal lifecycle."""

import json
import logging

from aimpro.lead import ReviewError, prepare_input
from aimpro.retrieval import evidence_from_response
from aimpro.syllabus import generate
from aimpro.syllabus_state import SyllabusResult, candidates, proposed_result
from document_search.contracts import SearchScope
from learning.context import LearningRequest
from learning.decisions import create_proposal, save_proposal
from learning.policies import authorize, scope_allows
from learning.store import StateConflict, canonical


def generate_syllabus(service, context_id, subject_key, project, *, request_id, authoring_factory,
                      source_scope, query=None, k=5, search_factory=None,
                      scenario='SCN01', competencies='elena_usecase_competencies', root_id=None, prepared_sources=None):
    if prepared_sources is not None:
        if query is not None or k != 5 or search_factory is not None:
            raise ValueError('Prepared sources cannot be combined with fresh retrieval options')
        from aimpro.source_service import generate_selected_syllabus
        return generate_selected_syllabus(service, context_id, subject_key, project, request_id=request_id,
            prepared_sources=prepared_sources, source_scope=source_scope, authoring_factory=authoring_factory,
            scenario=scenario, competencies=competencies, root_id=root_id)
    context = service._context(context_id, subject_key)
    root = context.snapshot.context
    authorize(service.policy, subject_key, 'propose', root.ref)
    if (not scope_allows(service.policy, source_scope, context_id, subject_key) or
            source_scope not in service.policy.scopes[source_scope].sources):
        raise ValueError('Syllabus corpus source scope is not authorized')
    if (not isinstance(query, str) or not query.strip() or type(k) is not int or
            not 1 <= k <= 20 or search_factory is None):
        raise ValueError('Syllabus requires a query, valid limit and search factory')
    LearningRequest(request_id=request_id, context_ref=root.ref, subject_key=subject_key,
                    text='Generate a Curator syllabus proposal', intent='CURATE')
    data = prepare_input(project, scenario=scenario, competencies=competencies, root_id=root_id)
    payload = canonical({'operation': 'AIMPRO_SYLLABUS_GENERATE', 'subject_key': subject_key,
        'source_sha256': data.source.source_sha256, 'metamodel_fingerprint': data.metamodel_fingerprint,
        'root_id': data.source.root_id, 'source_scope': source_scope, 'query': query.strip(), 'k': k})
    cached = service.store.request_result(request_id, context_id, payload)
    if cached is not None:
        return SyllabusResult.model_validate(cached)
    if (root.fields['mode'], root.fields['status']) != ('PREPARATION', 'DRAFT'):
        raise ValueError('Syllabus generation requires a PREPARATION DRAFT context')
    cached = service.store.claim_request(request_id, context_id, payload)
    if cached is not None:
        return SyllabusResult.model_validate(cached)
    attempts = ()
    try:
        response = search_factory()(query.strip(), k,
            scope=SearchScope(mode='PREPARATION', source_scope_keys=(source_scope,)))
        evidence = evidence_from_response(query.strip(), source_scope, k, response)
        if not evidence.resources:
            raise ReviewError('The search found no source for this query in this scope')
        data = data.model_copy(update={'corpus_evidence': evidence})
        dispatcher, lead, budget = authoring_factory()
        draft, verdict, attempts = generate(data, dispatcher=dispatcher, lead=lead, max_context_chars=budget)
        saved = candidates(data, draft, verdict, context)
        explanation = 'Import a Curator syllabus outline for human review, without teaching execution. ' + canonical({
            'source_sha256': data.source.source_sha256, 'metamodel_fingerprint': data.metamodel_fingerprint,
            'source_diagnostics': data.source.diagnostics, 'contract_findings': data.findings,
            'syllabus_gaps': draft.gaps,
            'remaining_work': ['Generate and review assessments and teaching materials',
                               'Approve exact resource bindings', 'Configure execution before activation']})
        proposal = create_proposal(context, (root.ref,), saved, explanation)
        result = proposed_result('Curator syllabus awaits human review; the outline remains a draft.',
                                 proposal, attempts, verdict)
        with service.store.write_transaction():
            if service.store.read_context(context_id).version != root.version:
                raise StateConflict('Context changed during syllabus generation')
            save_proposal(service.store, context, proposal, saved)
            service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
        return result
    except Exception as error:
        # ReviewError messages are fixed application text, never model or course content: the author may read them.
        reason = f' ({error})' if isinstance(error, ReviewError) else ''
        logging.getLogger('agent_system').warning('Syllabus generation failed (%s)%s', type(error).__name__, reason)
        result = SyllabusResult(kind='FAILURE', content=f'Syllabus generation did not complete{reason}; no proposal was applied.',
                                attempts=getattr(error, 'attempts', attempts))
    try:
        service.store.finish_request(request_id, context_id, result.model_dump(mode='json'))
    except StateConflict:
        return SyllabusResult.model_validate(service.store.claim_request(request_id, context_id, payload))
    return result


# The operations of the requests whose Curator drafts were reviewed: by a query, by prepared sources, a revision.
OPERATIONS = frozenset({'AIMPRO_SYLLABUS_GENERATE', 'AIMPRO_SELECTED_SYLLABUS', 'AIMPRO_SYLLABUS_REVISE'})


def syllabus_request(service, context_id, subject_key, request_id):
    """The subject's ended Curator syllabus request under ``request_id``, with its attempts; ``None`` otherwise."""
    with service.store.read_transaction():
        context = service._context(context_id, subject_key)
        authorize(service.policy, subject_key, 'propose', context.snapshot.context.ref)
        row = service.store.request_record(request_id, context_id)
    if row is None or row.result is None:
        return None
    payload = json.loads(row.payload)
    identity = payload.get('identity', payload)
    if identity.get('operation') not in OPERATIONS or identity.get('subject_key') != subject_key:
        return None
    return SyllabusResult.model_validate_json(row.result)
