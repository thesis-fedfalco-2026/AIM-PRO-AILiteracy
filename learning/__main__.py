from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

from learning.context import LearningRequest
from learning.contracts import EntityRef, entity_data
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract, validate_entity
from learning.policies import TrustedPolicy, authorize
from learning.service import LearningService
from learning.store import LearningStore


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Ciclo ALM locale con contesto e politica espliciti')
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--context', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('bootstrap')
    commands.add_parser('show')
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
    ask.add_argument('--ref', action='append', default=[], help='Riferimento contestuale in JSON')
    submit = commands.add_parser('submit')
    submit.add_argument('activity', help='EntityRef in JSON')
    submit.add_argument('content')
    submit.add_argument('--request-id', required=True)
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
                if input(f'Registrare {args.decision} per questo contenuto? Scrivere CONFERMO: ').strip() != 'CONFERMO':
                    print('Decisione non registrata.')
                    return 1
                result = entity_data(service.decide(args.context,args.subject,target,args.decision,args.reason))
            elif command == 'apply':
                result = entity_data(service.apply(args.context,args.subject,EntityRef.model_validate_json(args.proposal),args.operation_id))
            elif command == 'abandon':
                result = service.abandon_request(args.context,args.subject,args.request_id).model_dump(mode='json')
            elif command == 'submit':
                result = entity_data(service.submit(args.context,args.subject,EntityRef.model_validate_json(args.activity),args.content,args.request_id))
            else:
                request = LearningRequest(request_id=args.request_id or uuid4().hex,
                    context_ref=store.read_context(args.context).ref, subject_key=args.subject,text=args.question,
                    references=tuple(EntityRef.model_validate_json(ref) for ref in args.ref),intent=args.intent,
                    problem_key=args.problem_key,switch_from_socratic=args.switch_from_socratic)
                result = service.request(request).model_dump(mode='json')
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 1 if command != 'abandon' and result.get('kind') == 'FAILURE' else 0
    except (ValueError, OSError, KeyError, EOFError, sqlite3.Error):
        print('Operazione non eseguita: verificare contesto, autorizzazioni, riferimenti e formato dei dati.',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
