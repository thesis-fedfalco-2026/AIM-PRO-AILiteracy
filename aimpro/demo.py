"""Reproducible SCN01 colleague demo with explicit local review steps."""

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

from learning.context import LearningRequest
from learning.contracts import EntityRef, entity_data, make_entity
from learning.decisions import approval_valid, proposal_candidates
from learning.metamodel import load_contract, validate_entity
from learning.policies import TrustedPolicy
from learning.service import LearningService
from learning.store import LearningStore


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples/scn01/workshop.json'
CONTEXT = 'scn01-demo'
AUTHOR = 'demo-author'
LEARNER = 'demo-learner'
SCOPE = 'scn01-learning'


class DemoError(ValueError):
    """A fixed, source-free diagnostic suitable for the local runbook."""


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def init(directory):
    directory = Path(directory)
    if directory.exists():
        raise DemoError('Use a new run directory; existing demos are never reset automatically')
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    from aimpro.audit import DEFAULT_PROJECT
    if (fixture.get('format') != 'scn01-demo-workshop-v1' or fixture.get('synthetic_demo') is not True
            or hashlib.sha256(DEFAULT_PROJECT.read_bytes()).hexdigest() != fixture.get('source_sha256')):
        raise DemoError('The fixed demo fixture does not match its unchanged AIM-PRO source')
    contract = load_contract()
    entities = tuple(validate_entity(e, contract) for e in fixture['entities'])
    if any(contract.entity_types[e.type]['instanceLayer'] != 'domain_configuration' for e in entities):
        raise DemoError('Demo fixture must contain domain configuration only')
    activities = [e for e in entities if e.type == 'ActivityDefinition']
    resources = [e for e in entities if e.type == 'Resource' and
                 fixture['resource_key'] in e.provenance.sources]
    if len(resources) != 1:
        raise DemoError('Demo fixture requires one exact versioned corpus source')
    policy = TrustedPolicy.model_validate({'policy_ref': {'type': 'PolicySet', 'id': 'scn01-colleague-policy', 'version': '1'},
        'subjects': {
            AUTHOR: {'roles': ['ADMINISTRATOR', 'CONTENT_RESPONSIBLE', 'ASSESSOR'],
                     'actions': {CONTEXT: ['read', 'bootstrap', 'propose', 'decide', 'apply']}},
            LEARNER: {'roles': ['LEARNER'], 'actions': {CONTEXT: ['read', 'interact', 'submit']}}},
        'scopes': {
            'wp3': {'contexts': [CONTEXT], 'subjects': [AUTHOR], 'sources': ['wp3'], 'operations': ['read']},
            SCOPE: {'contexts': [CONTEXT], 'subjects': [AUTHOR, LEARNER],
                    'activities': [a.id for a in activities], 'resources': [fixture['resource_key']],
                    'sources': [], 'operations': ['read']}},
        'rule_bindings': [{'rule': e.ref.model_dump(), 'handler': 'all_completed'}
                          for e in entities if e.type == 'RuleDefinition']})
    directory.mkdir(parents=True)
    write(directory / 'policy.json', policy.model_dump(mode='json'))
    with LearningStore(directory / 'state.sqlite') as store:
        service = LearningService(store, contract, policy, lambda: None)
        root = service.bootstrap(CONTEXT, AUTHOR)
        bindings = [make_entity('ResourceBinding', f'demo-binding-{i}', {
            'context': root.ref.model_dump(), 'resource': resources[0].ref.model_dump(),
            'requirement': requirement, 'usageScope': SCOPE, 'valid': True, 'reviewPayloadKey': 'pending'},
            origin='GENERATED_PROPOSAL', responsible=AUTHOR)
            for i, requirement in enumerate(r for a in activities for r in a.fields['resourceRequirements'])]
        design = next(e for e in entities if e.type == 'LearningDesign')
        revised = root.model_copy(update={'version': uuid4().hex, 'fields': {**root.fields,
            'models': [e.ref.model_dump() for e in entities if e.type == 'DomainModel'],
            'learningDesign': design.ref.model_dump(), 'resourceBindings': [b.ref.model_dump() for b in bindings]},
            'provenance': root.provenance.model_copy(update={'origin': 'GENERATED_PROPOSAL', 'responsible': AUTHOR})})
        proposal = service.propose(CONTEXT, AUTHOR, (root.ref,), (*entities, *bindings, revised),
            'Import the fixed illustrative SCN01 demo workshop and exact source selections. '
            'All participants and subsequent example submissions are synthetic. Review this payload before import; no activation or progress is implied.')
        write(directory / 'manifest.json', {'fixture_sha256': hashlib.sha256(raw).hexdigest(),
            'import_proposal': proposal.ref.model_dump(), 'resource_key': fixture['resource_key']})
        write(directory / 'import-proposal.json', {'proposal': entity_data(proposal),
            'candidates': [entity_data(e) for e in proposal_candidates(store, proposal)]})
    return {'status': 'AWAITING_IMPORT_REVIEW', 'run_dir': str(directory),
            'review_file': str(directory / 'import-proposal.json')}


@contextmanager
def session(directory, *, live=False, model_profile=None, allow_paid=False):
    directory = Path(directory)
    policy = TrustedPolicy.model_validate_json((directory / 'policy.json').read_text())
    with LearningStore(directory / 'state.sqlite') as store:
        engines = []
        if live:
            def factory():
                from dotenv import load_dotenv
                from main import build_orchestrator
                from agent_system.config import load_model_catalog
                from crewai.events.utils.console_formatter import set_suppress_console_output
                load_dotenv(ROOT / '.env')
                set_suppress_console_output(True)
                catalog = load_model_catalog(ROOT / 'model.properties')
                if model_profile is not None:
                    # One explicit profile for Lead and every worker; paid use needs its own flag.
                    if model_profile not in catalog.profiles:
                        raise DemoError('Unknown model profile: ' + model_profile)
                    chosen = catalog.profiles[model_profile]
                    chosen = chosen.model_copy(update={'allow_paid': chosen.allow_paid or allow_paid})
                    catalog = catalog.model_copy(update={'profiles': {name: chosen for name in catalog.profiles}})
                catalog = catalog.model_copy(update={'settings': catalog.settings.model_copy(update={'timeout': 180}),
                    'orchestrator': catalog.orchestrator.model_copy(update={'max_steps': 1})})
                engine = build_orchestrator(model_catalog=catalog)
                engines.append(engine)
                write(directory / 'runtime-profile.json', {'lead_profile': model_profile or catalog.lead.profile,
                    'lead_model': catalog.profiles[catalog.lead.profile].model,
                    'paid_model_authorized': allow_paid,
                    'per_call_timeout_seconds': 180, 'max_steps': 1})
                return engine
        else:
            def factory():
                raise RuntimeError('This demo operation must not invoke a model')
        service = LearningService(store, load_contract(), policy, factory)
        service.demo_engines = engines
        yield service


def review_import(directory, *, confirm):
    if not confirm:
        raise DemoError('Review import-proposal.json, then use --confirm to record your local demo approval')
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    ref = EntityRef.model_validate(manifest['import_proposal'])
    with session(directory) as service:
        if service.store.operation_result('demo-import', CONTEXT):
            return {'status': 'ALREADY_IMPORTED'}
        service.decide(CONTEXT, AUTHOR, ref, 'APPROVE', 'Local operator explicitly confirmed the fixed synthetic demo fixture and source selections')
        change = service.apply(CONTEXT, AUTHOR, ref, 'demo-import')
        write(directory / 'import-application.json', entity_data(change))
    return {'status': 'IMPORTED_PREPARATION_DRAFT'}


def activate(directory, *, confirm):
    if not confirm:
        raise DemoError('Use --confirm to approve and apply demo activation')
    directory = Path(directory)
    with session(directory) as service:
        root = service.store.read_context(CONTEXT)
        if (root.fields['mode'], root.fields['status']) == ('LEARNING', 'ACTIVE'):
            return {'status': 'ALREADY_ACTIVE'}
        if not root.fields.get('learningDesign'):
            raise DemoError('Review and import the workshop before activation')
        active = root.model_copy(update={'version': uuid4().hex,
            'fields': {**root.fields, 'mode': 'LEARNING', 'status': 'ACTIVE'}})
        proposal = service.propose(CONTEXT, AUTHOR, (root.ref,), (active,),
            'Activate the explicitly reviewed synthetic colleague demo; preserve zero learner progress.')
        service.decide(CONTEXT, AUTHOR, proposal.ref, 'APPROVE', 'Local operator explicitly confirmed demo activation')
        change = service.apply(CONTEXT, AUTHOR, proposal.ref, 'demo-activate')
        write(directory / 'activation-application.json', entity_data(change))
    return {'status': 'LEARNING_ACTIVE'}


def ordered_activities(context):
    design = context.snapshot.get(context.snapshot.context.fields['learningDesign'])
    def visit(ref):
        node = context.snapshot.get(ref)
        if node.fields['kind'] == 'PHASE':
            return [a for child in node.fields['children'] for a in visit(child)]
        return [context.snapshot.get(a) for a in node.fields['activities']]
    return visit(design.fields['root'])


def submit(directory, answer_file, request_id):
    with session(directory) as service:
        context = service._context(CONTEXT, LEARNER)
        activity = [a for a in ordered_activities(context) if a.fields['intent'] == 'PRACTICE'][-1]
        evidence = service.submit(CONTEXT, LEARNER, activity.ref, Path(answer_file).read_text(), request_id)
        write(Path(directory) / 'latest-evidence.json', entity_data(evidence))
        return {'evidence': evidence.ref.model_dump(), 'status': 'IN_PROGRESS',
                'note': 'Submission records receipt only; no acquisition, grade or completion is inferred.'}


def ask(directory, role, request_id, *, model_profile=None, allow_paid=False):
    directory = Path(directory)
    with session(directory, live=True, model_profile=model_profile, allow_paid=allow_paid) as service:
        context = service._context(CONTEXT, LEARNER)
        intent = 'EXPLAIN' if role == 'teacher' else 'PRACTICE'
        choices = [a for a in ordered_activities(context) if a.fields['intent'] == intent]
        activity = choices[0] if role == 'teacher' else choices[-1]
        refs = ()
        if role == 'teacher':
            text = ('Use exactly one lesson-explainer Teacher step. Demonstrate a weak, worse and improved '
                'payment-reminder prompt using fictional data only; explain the choices. '
                'Do not invent workshop duration or expose internal task metadata. ')
        else:
            evidence = json.loads((directory / 'latest-evidence.json').read_text())
            refs = (EntityRef.model_validate({k: evidence[k] for k in ('type', 'id', 'version')}),)
            text = ('Use exactly one guided-practice-coach Trainer step. Give formative feedback on the supplied '
                'LearningEvidence: two strengths, two actionable improvements and one next-step question. '
                'Keep proposals empty; do not replace feedback with disclaimers. '
                'If marked synthetic, explicitly treat it as an operator-prepared demonstration. ')
        text += ('Use the exact requested activity. Retrieve only approved evidence with query "prompt engineering". '
                 'Give no grades, acquisition or completion claims. Respond in Italian.')
        request = LearningRequest(request_id=request_id, context_ref=context.snapshot.context.ref,
            subject_key=LEARNER, intent=intent, text=text, activity_refs=(activity.ref,), references=refs)
        write(directory / (role + '-request.json'), request.model_dump(mode='json'))
        response = service.request(request)
        write(directory / (role + '-records.json'), [entity_data(r) for engine in service.demo_engines
                                                   for r in engine.last_records])
        write(directory / (role + '-result.json'), response.model_dump(mode='json'))
        (directory / (role + '-answer.md')).write_text(response.content + '\n', encoding='utf-8')
        return response.model_dump(mode='json')


def status(directory):
    with session(directory) as service:
        context = service._context(CONTEXT, LEARNER)
        root = context.snapshot.context
        bindings = [context.snapshot.get(r) for r in root.fields['resourceBindings']]
        return {'mode': root.fields['mode'], 'status': root.fields['status'],
            'approved_bindings': sum(approval_valid(b, context.snapshot, service.policy) for b in bindings),
            'occurrence_statuses': [context.snapshot.get(r).fields['status'] for r in root.fields['activityOccurrences']],
            'learning_states': len(root.fields['learningStates']),
            'evaluations': len(service.store.owned(CONTEXT, 'Evaluation'))}


def check_sources(directory, *, environ=None):
    import os
    from dotenv import load_dotenv
    from agent_system.mcp_runtime import DocumentSearchClient, build_document_search_params
    from document_search.contracts import SearchScope
    with session(directory) as service:
        context = service._context(CONTEXT, LEARNER)
        if (context.snapshot.context.fields['mode'], context.snapshot.context.fields['status']) != ('LEARNING', 'ACTIVE'):
            raise DemoError('Activate the reviewed demo before its LEARNING source check')
        allowed = service.policy.scopes[SCOPE].resources
        if not all(approval_valid(context.snapshot.get(r), context.snapshot, service.policy)
                   for r in context.snapshot.context.fields['resourceBindings']):
            raise DemoError('Source bindings are not approved')
        if environ is None:
            load_dotenv(ROOT / '.env')
        result = DocumentSearchClient(build_document_search_params(ROOT, os.environ if environ is None else environ, unlimited_text=True)).search(
            'prompt engineering', 1, scope=SearchScope(mode='LEARNING', resource_keys=tuple(allowed)))
        write(Path(directory) / 'source-check.json', result)
        if not result['documents'] or result['truncated'] or any(d['metadata'].get('resource_key') not in allowed for d in result['documents']):
            raise DemoError('Approved snapshot unavailable or unexpected retrieval; check WP3 versions before model calls')
        return {'status': 'APPROVED_SOURCE_AVAILABLE', 'documents': len(result['documents']), 'resource_keys': allowed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('init', 'status', 'check-sources'):
        commands.add_parser(name)
    for name in ('approve-import', 'activate'):
        commands.add_parser(name).add_argument('--confirm', action='store_true')
    for name in ('teacher', 'trainer'):
        role = commands.add_parser(name)
        role.add_argument('--request-id', required=True)
        role.add_argument('--model-profile', help='Use this model.properties profile for Lead and all workers')
        role.add_argument('--allow-paid', action='store_true', help='Explicitly authorize a paid model profile')
    submission = commands.add_parser('submit')
    submission.add_argument('--answer-file', type=Path, required=True)
    submission.add_argument('--request-id', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init': result = init(args.run_dir)
        elif args.command == 'approve-import': result = review_import(args.run_dir, confirm=args.confirm)
        elif args.command == 'activate': result = activate(args.run_dir, confirm=args.confirm)
        elif args.command == 'submit': result = submit(args.run_dir, args.answer_file, args.request_id)
        elif args.command == 'status': result = status(args.run_dir)
        elif args.command == 'check-sources': result = check_sources(args.run_dir)
        else: result = ask(args.run_dir, args.command, args.request_id,
                           model_profile=args.model_profile, allow_paid=args.allow_paid)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('kind') == 'FAILURE' else 0
    except DemoError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError, StopIteration, RuntimeError):
        print('Demo operation did not complete. Check the run directory, stage, references and configuration.', file=sys.stderr)
        return 2
    finally:
        from agent_system.telemetry import flush
        flush()


if __name__ == '__main__':
    raise SystemExit(main())
