"""Read-only execution trace linked to unchanged AIM-PRO source identities.

This is an ALM sidecar format, never an instance of a new AIM-PRO class.
"""

import json

from aimpro.adapter import load_scenario
from aimpro.audit import DEFAULT_PROJECT
from aimpro.contracts import Contracts
from learning.context import references
from learning.decisions import review_payload_key
from learning.contracts import entity_data
from learning.store import StateConflict


RUNTIME_TYPES = ('ActivityOccurrence', 'LearningEvidence', 'Evaluation',
                 'LearningState', 'ChangeProposal', 'HumanDecision', 'StateChange')


def export_trace(store, context, project=DEFAULT_PROJECT, *, scenario='SCN01',
                 competencies='elena_usecase_competencies'):
    """Export context-owned history and candidate lineage under admin authority.

    Caller must hold a store read transaction for a consistent historical view.
    Source associations are provenance/reference links, never semantic equivalence.
    """
    roles = set(context.participant.fields['roles']) & set(
        context.policy.subjects[context.request.subject_key].roles)
    if 'ADMINISTRATOR' not in roles:
        raise ValueError('Execution history export requires administrative authority')
    source = load_scenario(project, scenario=scenario, competencies=competencies)
    contracts = Contracts(project)
    if contracts.source_sha256 != source.source_sha256:
        raise StateConflict('Source changed during trace export')
    source_index = {item.id: item for item in source.objects}
    root = context.snapshot.context
    if store.read_context(root.id).ref != root.ref:
        raise StateConflict('Context changed during trace export')

    # Include every context-owned revision, not only current reachable entities.
    history = list(store.history(root.id))
    entities = dict(context.snapshot.entities)
    entities.update((item.ref, item) for item in history)
    proposals = [item for item in history if item.type == 'ChangeProposal']
    pending = []
    for proposal in proposals:
        for item in store.candidates(proposal.ref):
            pending.append((proposal.ref, item))
            # Candidate revisions share immutable identities with applied entities.
            if item.ref in entities and entities[item.ref] != item:
                # Application attaches the reviewed approval link to bindings or
                # evaluations. Preserve both namespace payloads in the export.
                if (item.type not in {'ResourceBinding', 'Evaluation'} or
                        review_payload_key(item) != review_payload_key(entities[item.ref])):
                    raise ValueError('Conflicting candidate identity in trace')
            else:
                entities[item.ref] = item

    # Resolve domain revisions referenced by historical events as well as current
    # configuration. Never enumerate globally shared domain records.
    unavailable = set()
    queue = list(entities.values())
    while queue:
        item = queue.pop()
        for ref in references(item.fields):
            if ref in entities or ref in unavailable:
                continue
            try:
                linked = store.read(ref, owner=root.id)
            except ValueError:
                unavailable.add(ref)
                continue
            entities[ref] = linked
            queue.append(linked)

    links = {}
    diagnostics = [{'code': 'UNAVAILABLE_REFERENCE', 'entity': ref.model_dump()}
                   for ref in unavailable]
    for ref, item in entities.items():
        ids = set()
        for raw in item.provenance.sources:
            try:
                provenance = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(provenance, dict) or 'source_sha256' not in provenance:
                continue
            if (provenance.get('source_sha256') != source.source_sha256 or
                    provenance.get('metamodel_fingerprint') != contracts.fingerprint):
                diagnostics.append({'code': 'SOURCE_MISMATCH', 'entity': ref.model_dump()})
                continue
            claimed = provenance.get('source_ids', [])
            if not isinstance(claimed, list) or any(not isinstance(oid, str) for oid in claimed):
                raise ValueError('Invalid source lineage')
            for oid in claimed:
                if oid not in source_index:
                    diagnostics.append({'code': 'UNKNOWN_SOURCE_ID', 'entity': ref.model_dump(), 'source_id': oid})
                else:
                    ids.add(oid)
        links[ref] = ids

    # Do not spread context-wide lineage to every event through its context ref.
    # Follow causal, target, evidence and domain references, including proposal
    # candidates. Fixed-point propagation handles decision/proposal cycles.
    edges = {}
    for ref, item in entities.items():
        fields = {key: value for key, value in item.fields.items()
                  if key not in {'context', 'participants', 'policies', 'decider', 'learner'}}
        edges[ref] = tuple(r for r in references(fields)
                           if r in entities and r.type != 'ExecutionContext')
    changed = True
    while changed:
        changed = False
        for ref, targets in edges.items():
            inherited = set().union(*(links[target] for target in targets)) if targets else set()
            if not inherited <= links[ref]:
                links[ref].update(inherited)
                changed = True

    def record(item):
        return {'entity': entity_data(item), 'source_object_ids': sorted(links[item.ref]),
                'mapping': 'SOURCE_LINKED' if links[item.ref] else 'ALM_ONLY',
                'linked_entities': [r.model_dump() for r in sorted(edges[item.ref], key=lambda r: (r.type, r.id, r.version))]}

    used = set().union(*links.values()) if links else set()
    return {
        'format': 'aimpro-execution-trace', 'format_version': '1',
        'representation': 'ALM_SIDECAR', 'source_modified': False,
        'source': {'sha256': source.source_sha256, 'metamodel_fingerprint': contracts.fingerprint,
                   'scenario_model_id': source.scenario_model_id, 'scenario_root_id': source.root_id,
                   'objects': [source_index[oid].model_dump(mode='json') for oid in sorted(used)]},
        'context': root.ref.model_dump(),
        'runtime_representation': {kind: 'ALM_ONLY' for kind in RUNTIME_TYPES},
        'records': [record(item) for item in history],
        'definitions': [record(item) for ref, item in sorted(entities.items(), key=lambda pair: (pair[0].type, pair[0].id, pair[0].version))
                        if context.contract.entity_types[item.type]['instanceLayer'] == 'domain_configuration'],
        'candidates': [{'proposal': proposal.model_dump(), **record(item)} for proposal, item in pending],
        'diagnostics': sorted(diagnostics, key=lambda d: json.dumps(d, sort_keys=True)),
        'limitations': [
            'Runtime events remain ALM entities; source links do not make them AIM-PRO instances.',
            'Source provenance is recorded lineage, not proof of pedagogical equivalence or approval.',
            'No completion, acquisition, verification or evaluation is inferred by this export.',
            'Contains context-wide history and potentially learner data; intended for an authorized administrator.']}
