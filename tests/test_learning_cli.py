from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from learning.__main__ import main
from tests.test_learning_context import policy


class CLITest(unittest.TestCase):
    def test_help_needs_no_provider(self):
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit) as exit:
            main(['--help'])
        self.assertEqual(exit.exception.code, 0)

    def test_bootstrap_and_show(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp); (path/'policy.json').write_text(policy().model_dump_json())
            args=['--db',str(path/'state.sqlite'),'--policy',str(path/'policy.json'),'--context','session','--subject','admin']
            output=StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([*args,'bootstrap']),0)
                self.assertEqual(main([*args,'show']),0)
            self.assertIn('PREPARATION',output.getvalue())

    def test_abandon_pending_request_from_cli(self):
        from learning.store import LearningStore
        with TemporaryDirectory() as tmp:
            path=Path(tmp); (path/'policy.json').write_text(policy().model_dump_json())
            args=['--db',str(path/'state.sqlite'),'--policy',str(path/'policy.json'),'--context','session']
            with redirect_stdout(StringIO()):
                self.assertEqual(main([*args,'--subject','admin','bootstrap']),0)
            with LearningStore(path/'state.sqlite') as store:
                store.claim_request('orphan','session','{}')
            output=StringIO()
            with redirect_stderr(StringIO()):
                self.assertEqual(main([*args,'--subject','learner','abandon','orphan']),2)
            with redirect_stdout(output):
                self.assertEqual(main([*args,'--subject','admin','abandon','orphan']),0)
            self.assertIn('"kind": "FAILURE"',output.getvalue())

    def test_cli_error_does_not_expose_private_text(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp); (path/'policy.json').write_text('{"secret":"private prompt"}')
            output=StringIO()
            with redirect_stderr(output):
                self.assertEqual(main(['--db',str(path/'db'),'--policy',str(path/'policy.json'),
                                      '--context','session','--subject','admin','show']),2)
            self.assertNotIn('private prompt', output.getvalue())

    def test_malformed_bundle_is_rejected_without_traceback(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/'policy.json').write_text(policy().model_dump_json())
            args = ['--db', str(path/'state.sqlite'), '--policy', str(path/'policy.json'),
                    '--context', 'session', '--subject', 'admin']
            with redirect_stdout(StringIO()):
                self.assertEqual(main([*args, 'bootstrap']), 0)
            for bundle in (None, [], {'targets': None, 'candidates': []},
                           {'targets': [], 'candidates': None}):
                with self.subTest(bundle=bundle):
                    (path/'bundle.json').write_text(json.dumps(bundle))
                    error = StringIO()
                    with redirect_stderr(error):
                        self.assertEqual(main([*args, 'propose', str(path/'bundle.json')]), 2)
                    self.assertIn('Operation not performed', error.getvalue())
                    self.assertNotIn('Traceback', error.getvalue())

    def test_invalid_database_is_rejected_without_traceback(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/'policy.json').write_text(policy().model_dump_json())
            (path/'broken.sqlite').write_text('PRIVATE_DATABASE_CONTENT')
            for database in (path/'missing'/'state.sqlite', path/'broken.sqlite'):
                with self.subTest(database=database):
                    error = StringIO()
                    with redirect_stderr(error):
                        status = main(['--db', str(database), '--policy', str(path/'policy.json'),
                                       '--context', 'session', '--subject', 'admin', 'bootstrap'])
                    self.assertEqual(status, 2)
                    self.assertIn('Operation not performed', error.getvalue())
                    self.assertNotIn('Traceback', error.getvalue())
            self.assertEqual((path/'broken.sqlite').read_text(), 'PRIVATE_DATABASE_CONTENT')

    def test_real_provider_failure_does_not_expose_prompt(self):
        import logging
        from unittest.mock import patch
        from types import SimpleNamespace
        from crewai.events.event_bus import crewai_event_bus
        from crewai.events.utils.console_formatter import set_suppress_console_output, should_suppress_console_output
        from openai.resources.chat.completions import Completions
        from main import LLM
        from learning.store import LearningStore
        from learning.planning import LearningPlanDraft
        from smoke import prepare_demo
        sentinel='PRIVATE_USER_RESPONSE_SENTINEL'
        llm=LLM(provider='hosted_vllm',model='local-model',api_key='test',base_url='http://127.0.0.1:8000/v1')
        engine=SimpleNamespace(last_records=(),last_proposals=[],run=lambda request,**kwargs:llm.call(request.text,response_model=LearningPlanDraft))
        def emit_sync(source,event):
            crewai_event_bus._prepare_event(source,event)
            crewai_event_bus._call_handlers(source,event,crewai_event_bus._sync_handlers.get(type(event),frozenset()),crewai_event_bus._runtime_state)
        self.addCleanup(set_suppress_console_output,should_suppress_console_output())
        with TemporaryDirectory() as tmp:
            path=Path(tmp)
            with LearningStore(path/'state.sqlite') as store:
                service=prepare_demo(store,lambda:engine)
                (path/'policy.json').write_text(service.policy.model_dump_json())
            output,error=StringIO(),StringIO()
            handler=logging.StreamHandler(error); root=logging.getLogger(); root.addHandler(handler)
            self.addCleanup(root.removeHandler,handler)
            with patch('main.build_orchestrator',return_value=engine),patch.object(Completions,'parse',side_effect=ValueError(sentinel)) as provider,patch.object(crewai_event_bus,'emit',emit_sync),redirect_stdout(output),redirect_stderr(error):
                status=main(['--db',str(path/'state.sqlite'),'--policy',str(path/'policy.json'),
                    '--subject','learner','--context','demo','ask',sentinel])
            self.assertEqual(status,1)
            self.assertTrue(provider.called)
            self.assertNotIn(sentinel,output.getvalue()+error.getvalue())
