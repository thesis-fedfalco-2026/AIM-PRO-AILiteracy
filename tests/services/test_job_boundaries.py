"""Process boundaries of agent jobs (S08): only the worker holds models and credentials.

The API process authorizes and records job commands; it imports no model
client, no provider SDK, no MCP client and never reads ``.env``. The worker
builds the production factories lazily, so an idle worker builds nothing.
"""

import ast
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
# Model clients, provider SDKs, the MCP client, the agent runtime and the ``.env`` loader.
MODEL_CLIENTS = ('crewai', 'litellm', 'anthropic', 'openai', 'langfuse', 'mcp', 'dotenv', 'main',
                 'agent_system.anthropic', 'agent_system.openrouter', 'agent_system.runtime',
                 'agent_system.orchestrator', 'agent_system.mcp_runtime',
                 'learning.__main__', 'services.jobs.worker', 'services.jobs.__main__')
PROBE = '''
import json, sys
from services.authoring_api.app import schema_app
import services.authoring_api.__main__
schema_app()
roots = json.loads(sys.argv[1])
print(json.dumps(sorted(m for m in sys.modules if any(m == r or m.startswith(r + '.') for r in roots))))
'''


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


class ApiProcessTest(unittest.TestCase):
    def test_the_api_process_imports_no_model_client(self):
        env = {**os.environ, 'LANGFUSE_ENABLED': 'false', 'CREWAI_DISABLE_TELEMETRY': 'true',
               'CREWAI_TRACING_ENABLED': 'false'}
        result = subprocess.run([sys.executable, '-c', PROBE, json.dumps(MODEL_CLIENTS)], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_the_probe_detects_a_model_client(self):
        result = subprocess.run([sys.executable, '-c', 'import dotenv\n' + PROBE, json.dumps(MODEL_CLIENTS)],
                                cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('dotenv', json.loads(result.stdout))

    def test_api_modules_never_import_the_worker(self):
        for path in sorted((ROOT / 'services' / 'authoring_api').glob('*.py')):
            with self.subTest(path.name):
                found = [name for name in imports(path)
                         if any(name == f or name.startswith(f + '.') for f in MODEL_CLIENTS)]
                self.assertEqual(found, [])

    def test_the_jobs_library_used_by_the_api_imports_no_worker_code(self):
        for name in ('store.py', 'kinds.py'):
            with self.subTest(name):
                found = [m for m in imports(ROOT / 'services' / 'jobs' / name)
                         if any(m == f or m.startswith(f + '.') for f in MODEL_CLIENTS)]
                self.assertEqual(found, [])


class WorkerProcessTest(unittest.TestCase):
    def run_worker(self, *args, env=None):
        from services.jobs.__main__ import main
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output), patch.dict(os.environ, env or {}, clear=True):
            return main(list(args)), output.getvalue()

    def test_an_idle_worker_builds_no_model(self):
        from tests.seed import build_seed
        with TemporaryDirectory() as temp:
            root = Path(temp)
            seed = build_seed(root / 'seed', root / 'seed.sqlite')
            env = {'ALM_STORE': str(root / 'seed.sqlite'), 'ALM_POLICY_DIR': str(root / 'seed' / seed.policy_dir),
                   'ALM_JOBS_STORE': str(root / 'jobs.sqlite'), 'LANGFUSE_ENABLED': 'false'}
            with patch('services.jobs.__main__.production_resources') as production:
                status, output = self.run_worker('--once', env=env)
            self.assertEqual((status, output), (0, ''))
            production.assert_called_once_with(None)
            production.return_value.authoring.assert_not_called()
            self.assertTrue((root / 'jobs.sqlite').is_file())

    def test_the_worker_needs_its_stores_and_policies(self):
        status, output = self.run_worker('--once', env={})
        self.assertEqual(status, 2)
        self.assertIn('ALM_STORE', output)


if __name__ == '__main__':
    unittest.main()
