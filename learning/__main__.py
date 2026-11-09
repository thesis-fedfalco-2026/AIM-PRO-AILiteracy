from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

from learning.context import LearningRequest
from learning.contracts import EntityRef, entity_data
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract, validate_entity
from learning.policies import TrustedPolicy, authorize
from learning.releases import ActivationRefused
from learning.service import LearningService
from learning.store import LearningStore, database_errors


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Local ALM lifecycle with explicit context and policy')
    parser.add_argument('--db', required=True, help='SQLite file, sqlite:///path or postgresql:// URL')
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--context', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bootstrap')
    commands.add_parser('show')
    initialize = commands.add_parser('init-authoring-project', help='Propose a project from an approved/applied Curator syllabus')
    initialize.add_argument('project_id')
    initialize.add_argument('--syllabus', required=True, help='Exact syllabus Resource EntityRef JSON')
    initialize.add_argument('--base-context', required=True, help='Exact base ExecutionContext EntityRef JSON')
    initialize.add_argument('--request-id', required=True)
    revise = commands.add_parser('revise-authoring-project', help='Propose exact artifact selections and design definitions')
    revise.add_argument('bundle', type=Path, help='ProjectRevision JSON: project, base_context, design, artifacts, candidates, explanation')
    revise.add_argument('--request-id', required=True)
    inspect = commands.add_parser('show-authoring-project', help='Inspect current selections, approval receipts and stale dependencies')
    inspect.add_argument('project_id')
    pinned = commands.add_parser('show-project-syllabus', help='Resolve the approved syllabus through an exact current project revision')
    pinned.add_argument('project', help='Exact project Resource EntityRef JSON')
    release = commands.add_parser('propose-release', help='Propose a frozen release of the exact current project selection')
    release.add_argument('--project', required=True, help='Exact selected project Resource EntityRef JSON')
    release.add_argument('--domain', required=True, help='Exact project DomainModel EntityRef JSON')
    release.add_argument('--base-context', required=True, help='Exact base ExecutionContext EntityRef JSON')
    release.add_argument('--request-id', required=True)
    shown = commands.add_parser('show-release', help='Inspect release receipts, its exact frozen closure and findings')
    shown.add_argument('release', help='Exact release Resource EntityRef JSON')
    delivery = commands.add_parser('propose-delivery-import', help='Propose importing an applied release into this new delivery context')
    delivery.add_argument('bundle', type=Path, help='DeliveryImport JSON: release, authoring_context, base_context, scope_name, bindings, completion_handlers')
    delivery.add_argument('--request-id', required=True)
    delivery.add_argument('--policy-preview', type=Path, required=True, help='New file for the proposed trusted policy; does not replace the current policy')
    activation = commands.add_parser('propose-activation', help='Propose LEARNING/ACTIVE for an applied delivery import')
    activation.add_argument('--base-context', required=True, help='Exact base ExecutionContext EntityRef JSON')
    activation.add_argument('--request-id', required=True)
    for name in ('generate-project-assessments', 'generate-project-teacher', 'generate-project-trainer'):
        generator = commands.add_parser(name, help='Generate a typed pending authoring proposal from exact approved project inputs')
        generator.add_argument('bundle', type=Path, help='GenerationCommand JSON: project, base_context, assessments, shared_content, requirements')
        generator.add_argument('--request-id', required=True)
    propose = commands.add_parser('propose')
    propose.add_argument('bundle', type=Path, help='JSON: targets, candidates, explanation')
    decide = commands.add_parser('decide')
    decide.add_argument('target', help='EntityRef in JSON')
    decide.add_argument('decision', choices=['APPROVE','REJECT','REQUEST_REVISION'])
    decide.add_argument('--reason', required=True)
    apply = commands.add_parser('apply')
    apply.add_argument('proposal', help='EntityRef in JSON')
    apply.add_argument('--operation-id', required=True)
    abandon = commands.add_parser('abandon')
    abandon.add_argument('request_id')
    ask = commands.add_parser('ask')
    ask.add_argument('question')
    ask.add_argument('--request-id', default=None)
    ask.add_argument('--intent', choices=['EXPLAIN','PRACTICE','CURATE','ASSESS','SOCRATIC_GUIDANCE','CLARIFICATION','STATE'], default='EXPLAIN')
    ask.add_argument('--problem-key')
    ask.add_argument('--switch-from-socratic', action='store_true')
    ask.add_argument('--ref', action='append', default=[], help='Context reference in JSON')
    submit = commands.add_parser('submit')
    submit.add_argument('activity', help='EntityRef in JSON')
    submit.add_argument('content')
    submit.add_argument('--request-id', required=True)
    for name, description in (
        ('generate-aimpro', 'Generate a teaching draft as a pending local proposal'),
        ('generate-aimpro-syllabus', 'Delegate a corpus-grounded syllabus proposal to the Curator'),
    ):
        generate = commands.add_parser(name, help=description)
        generate.add_argument('project', type=Path)
        generate.add_argument('--request-id', required=True)
        generate.add_argument('--scenario', default='SCN01')
        generate.add_argument('--competencies', default='elena_usecase_competencies')
        generate.add_argument('--root-id')
        generate.add_argument('--source-scope', required=name == 'generate-aimpro-syllabus',
                              help='Explicit policy/source scope for corpus grounding')
        if name == 'generate-aimpro-syllabus':
            grounding = generate.add_mutually_exclusive_group(required=True)
            grounding.add_argument('--query', help='Single corpus search query')
            grounding.add_argument('--prepared-sources', help='Exact completed source-preparation request id in this context')
        else:
            generate.add_argument('--query', help='Corpus search query, required with --source-scope')
        generate.add_argument('--k', type=int, default=5, choices=range(1, 21))
    sources = commands.add_parser('prepare-aimpro-syllabus-sources', help='Prepare multi-query exact Curator excerpts without models')
    sources.add_argument('project', type=Path)
    sources.add_argument('--plan', type=Path, required=True)
    sources.add_argument('--request-id', required=True)
    sources.add_argument('--scenario', default='SCN01')
    sources.add_argument('--competencies', default='elena_usecase_competencies')
    sources.add_argument('--root-id')
    syllabus = commands.add_parser('show-aimpro-syllabus', help='Resolve the exact approved/applied current syllabus')
    syllabus.add_argument('design', help='Current LearningDesign EntityRef in JSON')
    trace = commands.add_parser('export-aimpro-trace', help='Read-only ALM execution history linked to unchanged AIM-PRO objects')
    trace.add_argument('project', type=Path)
    trace.add_argument('--scenario', default='SCN01')
    trace.add_argument('--competencies', default='elena_usecase_competencies')
    bindings = commands.add_parser('propose-aimpro-bindings', help='Propose explicit resource selections with a pending teaching design')
    bindings.add_argument('proposal', help='Pending teaching ChangeProposal EntityRef in JSON')
    bindings.add_argument('selections', type=Path, help='JSON list: activity, requirement, resource EntityRefs and usage_scope')
    setup = commands.add_parser('prepare-aimpro-execution', help='Propose reviewed worker, learner-scope and completion configuration')
    setup.add_argument('--learner', required=True)
    setup.add_argument('--learning-scope')
    setup.add_argument('--policy-preview', type=Path, required=True, help='New file for the proposed trusted policy; does not replace the current policy')
    return parser.parse_args(argv)


def _orchestrator():
    from dotenv import load_dotenv
    from main import BASE_DIR, build_orchestrator
    load_dotenv(BASE_DIR / '.env')
    from crewai.events.utils.console_formatter import set_suppress_console_output
    set_suppress_console_output(True)
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    for handler in logging.getLogger().handlers:
        handler.addFilter(logging.Filter('agent_system'))
    return build_orchestrator()


def _aimpro_lead():
    from main import build_aimpro_lead
    from crewai.events.utils.console_formatter import set_suppress_console_output
    set_suppress_console_output(True)
    return build_aimpro_lead()


def _aimpro_search():
    return _aimpro_search_client().search


def _aimpro_search_client():
    import os
    from dotenv import load_dotenv
    from agent_system.mcp_runtime import DocumentSearchClient, build_document_search_params
    base_dir = Path(__file__).resolve().parents[1]
    load_dotenv(base_dir / '.env')
    return DocumentSearchClient(build_document_search_params(base_dir, os.environ, unlimited_text=True))


def _aimpro_authoring():
    from main import build_aimpro_authoring
    from crewai.events.utils.console_formatter import set_suppress_console_output
    set_suppress_console_output(True)
    return build_aimpro_authoring()


def main(argv=None):
    args = parse_args(argv)
    try:
        contract = load_contract()
        policy = TrustedPolicy.model_validate(json.loads(args.policy.read_text()))
        if policy.policy_ref.type != 'PolicySet':
            raise ValueError('Invalid policy reference')
        with LearningStore(args.db) as store:
            service = LearningService(store,contract,policy,_orchestrator)
            command = args.command
            if command == 'bootstrap':
                result = entity_data(service.bootstrap(args.context,args.subject))
            elif command == 'show':
                result = service.show(args.context,args.subject)
            elif command == 'init-authoring-project':
                result = service.initialize_authoring_project(args.context, args.subject, {
                    'project_id': args.project_id, 'syllabus': EntityRef.model_validate_json(args.syllabus),
                    'base_context': EntityRef.model_validate_json(args.base_context)},
                    request_id=args.request_id).model_dump(mode='json')
            elif command == 'revise-authoring-project':
                result = service.revise_authoring_project(args.context, args.subject,
                    json.loads(args.bundle.read_text()), request_id=args.request_id).model_dump(mode='json')
            elif command == 'show-authoring-project':
                result = service.inspect_authoring_project(args.context, args.subject, args.project_id).model_dump(mode='json')
            elif command == 'show-project-syllabus':
                result = service.approved_project_syllabus(args.context, args.subject,
                    EntityRef.model_validate_json(args.project)).model_dump(mode='json')
            elif command == 'propose-release':
                result = service.propose_release(args.context, args.subject, {
                    'project': EntityRef.model_validate_json(args.project),
                    'domain': EntityRef.model_validate_json(args.domain),
                    'base_context': EntityRef.model_validate_json(args.base_context)},
                    request_id=args.request_id).model_dump(mode='json')
            elif command == 'show-release':
                result = service.inspect_release(args.context, args.subject,
                    EntityRef.model_validate_json(args.release)).model_dump(mode='json')
            elif command == 'propose-delivery-import':
                if args.policy_preview.exists() or not args.policy_preview.parent.is_dir():
                    raise ValueError('Choose a new policy preview file in an existing directory')
                result = service.propose_delivery_import(args.context, args.subject,
                    json.loads(args.bundle.read_text()), request_id=args.request_id).model_dump(mode='json')
                with args.policy_preview.open('x', encoding='utf-8') as preview:
                    json.dump(result['policy_preview'], preview, ensure_ascii=False, indent=2)
                    preview.write('\n')
            elif command == 'propose-activation':
                result = service.propose_activation(args.context, args.subject,
                    {'base_context': EntityRef.model_validate_json(args.base_context)},
                    request_id=args.request_id).model_dump(mode='json')
            elif command in ('generate-project-assessments', 'generate-project-teacher', 'generate-project-trainer'):
                method = getattr(service, command.replace('-', '_'))
                result = method(args.context, args.subject, json.loads(args.bundle.read_text()),
                    request_id=args.request_id, authoring_factory=_aimpro_authoring).model_dump(mode='json')
            elif command == 'propose':
                bundle = json.loads(args.bundle.read_text())
                if not isinstance(bundle, dict) or any(
                    not isinstance(bundle.get(key), list) for key in ('targets', 'candidates')
                ):
                    raise ValueError('Invalid proposal bundle')
                result = entity_data(service.propose(args.context,args.subject,
                    tuple(EntityRef.model_validate(ref) for ref in bundle['targets']),
                    tuple(validate_entity(item,contract) for item in bundle['candidates']),bundle['explanation']))
            elif command == 'decide':
                context = service._context(args.context,args.subject)
                authorize(policy,args.subject,'decide',context.snapshot.context.ref)
                target = EntityRef.model_validate_json(args.target)
                entity = store.read(target, owner=args.context)
                candidates = proposal_candidates(store,entity) if entity.type == 'ChangeProposal' else ()
                print(json.dumps({'target':entity_data(entity),'candidates':[entity_data(c) for c in candidates]}, ensure_ascii=False,indent=2))
                if input(f'Record {args.decision} for this content? Type CONFIRM: ').strip() != 'CONFIRM':
                    print('Decision not recorded.')
                    return 1
                result = entity_data(service.decide(args.context,args.subject,target,args.decision,args.reason))
            elif command == 'apply':
                result = entity_data(service.apply(args.context,args.subject,EntityRef.model_validate_json(args.proposal),args.operation_id))
            elif command == 'abandon':
                result = service.abandon_request(args.context,args.subject,args.request_id).model_dump(mode='json')
            elif command == 'submit':
                result = entity_data(service.submit(args.context,args.subject,EntityRef.model_validate_json(args.activity),args.content,args.request_id))
            elif command == 'export-aimpro-trace':
                result = service.export_aimpro_trace(args.context, args.subject, args.project,
                    scenario=args.scenario, competencies=args.competencies)
            elif command == 'prepare-aimpro-execution':
                if args.policy_preview.exists() or not args.policy_preview.parent.is_dir():
                    raise ValueError('Choose a new policy preview file in an existing directory')
                result = service.prepare_aimpro_execution(args.context, args.subject,
                    learner=args.learner, scope_name=args.learning_scope)
                with args.policy_preview.open('x', encoding='utf-8') as preview:
                    json.dump(result['policy_preview'], preview, ensure_ascii=False, indent=2)
                    preview.write('\n')
            elif command == 'propose-aimpro-bindings':
                result = entity_data(service.propose_aimpro_bindings(args.context, args.subject,
                    EntityRef.model_validate_json(args.proposal), json.loads(args.selections.read_text())))
            elif command == 'generate-aimpro':
                result = service.generate_aimpro(args.context, args.subject, args.project,
                    request_id=args.request_id, lead_factory=_aimpro_lead,
                    scenario=args.scenario, competencies=args.competencies, root_id=args.root_id,
                    source_scope=args.source_scope, query=args.query, k=args.k,
                    search_factory=_aimpro_search if args.source_scope else None).model_dump(mode='json')
            elif command == 'generate-aimpro-syllabus':
                result = service.generate_aimpro_syllabus(args.context, args.subject, args.project,
                    request_id=args.request_id, authoring_factory=_aimpro_authoring,
                    scenario=args.scenario, competencies=args.competencies, root_id=args.root_id,
                    source_scope=args.source_scope, query=args.query, k=args.k,
                    search_factory=_aimpro_search if args.prepared_sources is None else None,
                    prepared_sources=args.prepared_sources).model_dump(mode='json')
            elif command == 'prepare-aimpro-syllabus-sources':
                result = service.prepare_aimpro_syllabus_sources(args.context, args.subject, args.project,
                    json.loads(args.plan.read_text()), request_id=args.request_id,
                    search_client_factory=_aimpro_search_client, scenario=args.scenario,
                    competencies=args.competencies, root_id=args.root_id).model_dump(mode='json')
            elif command == 'show-aimpro-syllabus':
                result = service.approved_aimpro_syllabus(args.context, args.subject,
                    EntityRef.model_validate_json(args.design)).model_dump(mode='json')
            else:
                request = LearningRequest(request_id=args.request_id or uuid4().hex,
                    context_ref=store.read_context(args.context).ref, subject_key=args.subject,text=args.question,
                    references=tuple(EntityRef.model_validate_json(ref) for ref in args.ref),intent=args.intent,
                    problem_key=args.problem_key,switch_from_socratic=args.switch_from_socratic)
                result = service.request(request).model_dump(mode='json')
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 1 if command != 'abandon' and result.get('kind') == 'FAILURE' else 0
    except ActivationRefused as error:
        print(json.dumps({'refused': 'activation', 'findings': [f.model_dump() for f in error.findings]},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError, EOFError, *database_errors()):
        print('Operation not performed: check the context, permissions, references and data format.',file=sys.stderr)
        return 2


_command_main = main


def main(argv=None):
    from agent_system.telemetry import flush
    try:
        return _command_main(argv)
    finally:
        flush()


if __name__ == '__main__':
    raise SystemExit(main())
