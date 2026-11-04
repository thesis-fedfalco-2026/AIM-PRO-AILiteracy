from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from aimpro import demo
from learning.outputs import LearningResponse


class DemoRunbookTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fresh-demo'
        demo.init(self.path)

    def activate(self):
        demo.review_import(self.path, confirm=True)
        demo.activate(self.path, confirm=True)

    def test_fresh_fixture_needs_explicit_review_and_activation(self):
        self.assertEqual(demo.status(self.path)['mode'], 'PREPARATION')
        with self.assertRaises(ValueError):demo.review_import(self.path, confirm=False)
        with self.assertRaises(ValueError):demo.activate(self.path, confirm=True)
        demo.review_import(self.path, confirm=True)
        self.assertEqual(demo.status(self.path)['approved_bindings'], 5)
        self.assertEqual(demo.status(self.path)['status'], 'DRAFT')
        with self.assertRaises(ValueError):demo.activate(self.path, confirm=False)
        demo.activate(self.path, confirm=True)
        self.assertEqual(demo.status(self.path), {'mode': 'LEARNING', 'status': 'ACTIVE',
            'approved_bindings': 5, 'occurrence_statuses': [], 'learning_states': 0, 'evaluations': 0})
        self.assertEqual(demo.review_import(self.path, confirm=True)['status'], 'ALREADY_IMPORTED')
        self.assertEqual(demo.activate(self.path, confirm=True)['status'], 'ALREADY_ACTIVE')

    def test_existing_directory_is_never_reset(self):
        original = (self.path / 'manifest.json').read_bytes()
        with self.assertRaises(ValueError):demo.init(self.path)
        self.assertEqual((self.path / 'manifest.json').read_bytes(), original)

    def test_synthetic_submission_is_in_progress_and_replays_without_duplicates(self):
        self.activate()
        first = demo.submit(self.path, demo.ROOT / 'examples/scn01/synthetic-attempt.txt', 'attempt-1')
        second = demo.submit(self.path, demo.ROOT / 'examples/scn01/synthetic-attempt.txt', 'attempt-1')
        self.assertEqual(first, second)
        state = demo.status(self.path)
        self.assertEqual(state['occurrence_statuses'], ['IN_PROGRESS'])
        self.assertEqual(state['learning_states'], 0)
        self.assertEqual(state['evaluations'], 0)

    def test_teacher_and_trainer_resolve_current_activity_and_evidence_refs(self):
        self.activate()
        with patch('learning.service.LearningService.request', return_value=LearningResponse(kind='ANSWER',content='Test explanation')) as request:
            demo.ask(self.path, 'teacher', 'teacher-1')
            self.assertEqual(request.call_args.args[0].intent, 'EXPLAIN')
            self.assertEqual(len(request.call_args.args[0].activity_refs), 1)
        with patch('learning.service.LearningService.request') as request:
            with self.assertRaises(OSError):demo.ask(self.path, 'trainer', 'trainer-missing')
            request.assert_not_called()
        evidence = demo.submit(self.path, demo.ROOT / 'examples/scn01/synthetic-attempt.txt', 'attempt-1')
        with patch('learning.service.LearningService.request', return_value=LearningResponse(kind='ANSWER',content='Test feedback')) as request:
            demo.ask(self.path, 'trainer', 'trainer-1')
            self.assertEqual(request.call_args.args[0].intent, 'PRACTICE')
            self.assertEqual(request.call_args.args[0].references[0].model_dump(), evidence['evidence'])
        self.assertEqual((self.path / 'trainer-answer.md').read_text(), 'Test feedback\n')

    def test_model_profile_override_applies_to_every_role_and_paid_needs_its_own_flag(self):
        for allow_paid in (False, True):
            with self.subTest(allow_paid=allow_paid), patch('dotenv.load_dotenv'), \
                    patch('main.build_orchestrator') as build:
                with demo.session(self.path, live=True, model_profile='anthropic', allow_paid=allow_paid) as service:
                    service.orchestrator_factory()
                catalog = build.call_args.kwargs['model_catalog']
                self.assertEqual({p.provider for p in catalog.profiles.values()}, {'anthropic'})
                self.assertEqual({p.allow_paid for p in catalog.profiles.values()}, {allow_paid})
                runtime = json.loads((self.path / 'runtime-profile.json').read_text())
                self.assertEqual((runtime['lead_profile'], runtime['paid_model_authorized']), ('anthropic', allow_paid))
        with patch('dotenv.load_dotenv'), self.assertRaisesRegex(demo.DemoError, 'Unknown model profile'):
            with demo.session(self.path, live=True, model_profile='missing') as service:
                service.orchestrator_factory()

    def test_cli_status_and_confirmation_diagnostics(self):
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(demo.main(['--run-dir',str(self.path),'status']),0)
        self.assertEqual(json.loads(output.getvalue())['status'],'DRAFT')
        with redirect_stderr(StringIO()) as error:
            self.assertEqual(demo.main(['--run-dir',str(self.path),'approve-import']),2)
        self.assertIn('--confirm',error.getvalue())

    @unittest.skipUnless(os.environ.get('WP3_TEST_DATABASE_URL'), 'Requires real WP3 reader database')
    def test_fresh_demo_retrieves_its_exact_approved_snapshot_through_mcp(self):
        self.activate()
        result = demo.check_sources(self.path, environ={'SEARCH_BACKEND':'postgres',
            'WP3_DATABASE_URL':os.environ['WP3_TEST_DATABASE_URL']})
        self.assertEqual(result['status'],'APPROVED_SOURCE_AVAILABLE')
        self.assertEqual(len(result['resource_keys']),1)
        self.assertEqual(result['documents'],1)
