"""Policy resolution (D10), per-request services and Authoring API configuration (S05)."""

import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from learning.contracts import EntityRef
from services.api_common.contexts import (ContextServices, ContextUnavailable, PolicyDirectory,
                                          PolicyDirectoryError)
from services.api_common.registry import ConfigurationError
from services.api_common.settings import ApiSettings
from services.authoring_api.app import REGISTRY, create_app
from tests.authoring_cycle_fixtures import AUTH, DELIVERY, trusted_policy
from tests.seed import build_seed
from tests.services.oidc_fixtures import NO_NETWORK, FakeProvider, auth_settings, write_identity_map
from tests.store_backends import block_network


ROOT = Path(__file__).resolve().parents[2]
POLICY_REF = trusted_policy().policy_ref


def write_policy(directory, name, policy=None):
    path = Path(directory) / name
    path.write_text((policy or trusted_policy()).model_dump_json(), encoding='utf-8')
    return path


class PolicyDirectoryTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)

    def test_finds_the_file_whose_policy_ref_equals_the_reference(self):
        write_policy(self.directory, 'policy.json')
        (self.directory / 'README.txt').write_text('not a policy', encoding='utf-8')
        (self.directory / 'nested').mkdir()
        write_policy(self.directory / 'nested', 'other.json', trusted_policy().model_copy(
            update={'policy_ref': EntityRef(type='PolicySet', id='nested', version='1')}))
        policies = PolicyDirectory(self.directory)
        self.assertEqual(policies.find(POLICY_REF), trusted_policy())
        self.assertIsNone(policies.find(POLICY_REF.model_copy(update={'version': '2'})))
        self.assertIsNone(policies.find(EntityRef(type='PolicySet', id='nested', version='1')))

    def test_a_policy_installed_later_is_found_without_restart(self):
        policies = PolicyDirectory(self.directory)
        self.assertIsNone(policies.find(POLICY_REF))
        write_policy(self.directory, 'installed.json')
        self.assertEqual(policies.find(POLICY_REF), trusted_policy())

    def test_a_reference_installed_twice_or_an_invalid_file_refuses_resolution(self):
        write_policy(self.directory, 'a.json')
        write_policy(self.directory, 'b.json')
        with self.assertRaisesRegex(PolicyDirectoryError, 'more than one file'):
            PolicyDirectory(self.directory).find(POLICY_REF)
        (self.directory / 'b.json').write_text('{"secret": "private policy text"}', encoding='utf-8')
        with self.assertRaises(PolicyDirectoryError) as refused:
            PolicyDirectory(self.directory).find(POLICY_REF)
        self.assertIn('b.json', str(refused.exception))
        self.assertNotIn('private policy text', str(refused.exception))
        self.assertNotIsInstance(refused.exception, ValueError)

    def test_the_directory_must_exist(self):
        with self.assertRaises(ConfigurationError):
            PolicyDirectory(self.directory / 'missing')


class ContextServicesTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.seed = build_seed(self.root / 'seed')
        self.location = self.root / 'seed' / self.seed.store
        self.services = ContextServices(str(self.location), PolicyDirectory(self.root / 'seed' / self.seed.policy_dir))

    def test_opens_a_service_with_the_policy_of_the_context(self):
        with self.services.open(AUTH) as service:
            self.assertEqual(service.policy, trusted_policy())
            self.assertEqual(service.show(AUTH, 'admin')['context']['id'], AUTH)
            with self.assertRaises(RuntimeError):
                service.orchestrator_factory()

    def test_unknown_context_and_missing_policy_are_unavailable(self):
        for context_id, reason in (('no-such-context', 'no such context'), (DELIVERY, 'policy not installed')):
            with self.subTest(context_id), self.assertRaises(ContextUnavailable) as refused:
                with self.services.open(context_id):
                    self.fail('A service was opened')
            self.assertEqual(refused.exception.reason, reason)
            self.assertEqual(str(refused.exception), 'Context unavailable')

    def test_a_missing_sqlite_file_is_refused_and_never_created(self):
        missing = self.root / 'missing.sqlite'
        with self.assertRaisesRegex(ConfigurationError, 'ALM_STORE'):
            ContextServices(str(missing), PolicyDirectory(self.root))
        self.assertFalse(missing.exists())


class AuthoringConfigurationTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.identities = write_identity_map(self.root)

    def settings(self, **values):
        return ApiSettings(auth=auth_settings(), identity_map=self.identities, **values)

    def test_settings_read_the_store_and_policy_directory_without_exposing_the_url(self):
        env = {'ALM_OIDC_ISSUER': 'https://idp.test', 'ALM_OIDC_CLIENT_ID': 'c', 'ALM_OIDC_CLIENT_SECRET': 's',
               'ALM_OIDC_REDIRECT_URI': 'https://api.test/auth/callback', 'ALM_IDENTITY_MAP': 'map.json',
               'ALM_STORE': 'postgresql://alm:db-password@127.0.0.1/alm', 'ALM_POLICY_DIR': 'policies'}
        settings = ApiSettings.from_env(env)
        self.assertEqual(settings.store.get_secret_value(), env['ALM_STORE'])
        self.assertEqual(settings.policy_dir, Path('policies'))
        self.assertNotIn('db-password', repr(settings))
        bare = ApiSettings.from_env({k: v for k, v in env.items() if k not in ('ALM_STORE', 'ALM_POLICY_DIR')})
        self.assertIsNone(bare.store)
        self.assertIsNone(bare.policy_dir)

    def test_authoring_modules_need_a_store_and_a_policy_directory(self):
        for values in ({}, {'store': str(self.root / 'x.sqlite')}, {'policy_dir': self.root}):
            with self.subTest(values), self.assertRaisesRegex(ConfigurationError, 'ALM_STORE and ALM_POLICY_DIR'):
                create_app(self.settings(**values), transport=FakeProvider().transport)
        identity_only = create_app(self.settings(modules=()), transport=FakeProvider().transport)
        self.assertEqual(TestClient(identity_only).get('/contexts/x').status_code, 404)

    def test_every_authoring_module_is_registered(self):
        self.assertEqual(REGISTRY.names, ('contexts', 'review', 'projects', 'releases', 'jobs'))


class ModuleBoundaryTest(unittest.TestCase):
    """Module rule 3: authoring modules reach the core only through LearningService and its records."""

    FORBIDDEN = ('learning.store', 'learning.decisions')

    def imports(self, path):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                yield from (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                yield node.module

    def test_authoring_modules_never_import_store_or_decision_internals(self):
        modules = sorted((ROOT / 'services' / 'authoring_api').glob('*.py'))
        self.assertTrue({'review.py', 'projects.py', 'releases.py', 'context_summary.py'} <= {p.name for p in modules})
        for path in modules:
            with self.subTest(path.name):
                found = [name for name in self.imports(path)
                         if any(name == f or name.startswith(f + '.') for f in self.FORBIDDEN)]
                self.assertEqual(found, [])

    def test_the_detector_sees_both_import_forms(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / 'module.py'
            path.write_text('import learning.store\nfrom learning.decisions import x\n', encoding='utf-8')
            self.assertEqual(list(self.imports(path)), ['learning.store', 'learning.decisions'])


if __name__ == '__main__':
    unittest.main()
