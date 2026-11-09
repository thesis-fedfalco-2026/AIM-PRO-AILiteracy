"""App factory, module registry, error mapping and request ids of the API skeleton (S03)."""

import re
import unittest

from fastapi import APIRouter, Depends

from learning.contracts import EntityRef
from learning.policies import AuthorizationError, TrustedPolicy, authorize
from learning.store import StateConflict
from services.api_common.auth import csrf_protected
from services.api_common.registry import ApiModule, ConfigurationError, ModuleRegistry
from services.api_common.request_ids import REQUEST_ID_HEADER, current_request_id
from services.api_common.settings import ApiSettings
from tests.services.oidc_fixtures import NO_NETWORK, FakeProvider, api_client
from tests.store_backends import block_network


PRIVATE = 'private learner answer'
CONTEXT = EntityRef(type='ExecutionContext', id='session', version='1')
POLICY = TrustedPolicy.model_validate({
    'policy_ref': {'type': 'PolicySet', 'id': 'policy', 'version': '1'},
    'subjects': {'learner': {'roles': ['LEARNER'], 'actions': {'session': ['read']}}}})


def failing_module():
    router = APIRouter(prefix='/fail')

    @router.get('/conflict')
    def conflict():
        raise StateConflict('Proposal base is stale')

    @router.get('/forbidden')
    def forbidden():
        authorize(POLICY, 'learner', 'apply', CONTEXT)

    @router.get('/invalid')
    def invalid():
        raise ValueError('Base context belongs to another context')

    @router.get('/record')
    def record():
        EntityRef.model_validate({'type': 'Resource', 'id': PRIVATE, 'version': 1})

    @router.get('/query')
    def typed_query(count: int):
        return {'count': count}

    @router.get('/crash')
    def crash():
        raise RuntimeError(PRIVATE)

    @router.get('/request-id')
    def request_id():
        return {'request_id': current_request_id()}

    return ApiModule('failing', router)


def module(name, path):
    router = APIRouter()
    router.add_api_route(path, lambda: {'module': name}, methods=['GET'])
    return ApiModule(name, router)


class AuthorizationErrorTest(unittest.TestCase):
    def test_authorize_raises_a_distinct_error_that_is_still_a_value_error(self):
        with self.assertRaises(AuthorizationError) as raised:
            authorize(POLICY, 'learner', 'apply', CONTEXT)
        self.assertIsInstance(raised.exception, ValueError)
        self.assertEqual(str(raised.exception), 'Action is not authorized in this context')
        for subject, action, context in (('nobody', 'read', CONTEXT), ('learner', 'read', CONTEXT.model_copy(update={'type': 'Resource'}))):
            with self.subTest(subject=subject, context=context.type):
                self.assertRaises(AuthorizationError, authorize, POLICY, subject, action, context)
        self.assertIsNone(authorize(POLICY, 'learner', 'read', CONTEXT))


class ErrorMappingTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        self.client = api_client(FakeProvider(), (failing_module(),))

    def assert_error(self, path, status, error, detail=None):
        response = self.client.get(path, headers={REQUEST_ID_HEADER: 'req-' + error})
        self.assertEqual(response.status_code, status, response.text)
        body = response.json()
        self.assertEqual(set(body), {'error', 'detail', 'request_id'})
        self.assertEqual(body['error'], error)
        self.assertEqual(body['request_id'], 'req-' + error)
        self.assertEqual(response.headers[REQUEST_ID_HEADER], 'req-' + error)
        self.assertNotIn(PRIVATE, response.text)
        if detail is not None:
            self.assertEqual(body['detail'], detail)
        return body

    def test_state_conflict_is_409(self):
        self.assert_error('/fail/conflict', 409, 'conflict', 'Proposal base is stale')

    def test_authorization_failure_is_403(self):
        self.assert_error('/fail/forbidden', 403, 'forbidden', 'Action is not authorized')

    def test_value_error_is_422(self):
        self.assert_error('/fail/invalid', 422, 'validation', 'Base context belongs to another context')

    def test_record_validation_is_422_without_input_values(self):
        body = self.assert_error('/fail/record', 422, 'validation')
        self.assertEqual([item['loc'] for item in body['detail']], [['version']])
        self.assertEqual(set(body['detail'][0]), {'loc', 'msg', 'type'})

    def test_request_validation_is_422_without_input_values(self):
        response = self.client.get('/fail/query', params={'count': PRIVATE})
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body['error'], 'validation')
        self.assertEqual([item['loc'] for item in body['detail']], [['query', 'count']])
        self.assertNotIn(PRIVATE, response.text)

    def test_anything_else_is_500_without_detail(self):
        with self.assertLogs('services.api_common', 'ERROR') as logs:
            self.assert_error('/fail/crash', 500, 'internal', 'Internal error')
        self.assertIn('req-internal', '\n'.join(logs.output))

    def test_unknown_route_uses_the_same_error_shape(self):
        self.assert_error('/missing', 404, 'not_found')
        response = self.client.delete('/health')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['error'], 'method_not_allowed')


class RequestIdTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        self.client = api_client(FakeProvider(), (failing_module(),))

    def test_health_needs_no_session_and_gets_a_new_request_id(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertRegex(response.headers[REQUEST_ID_HEADER], r'^[0-9a-f]{32}$')
        self.assertNotEqual(self.client.get('/health').headers[REQUEST_ID_HEADER], response.headers[REQUEST_ID_HEADER])

    def test_a_valid_client_request_id_is_propagated_to_the_handler_and_the_response(self):
        response = self.client.get('/fail/request-id', headers={REQUEST_ID_HEADER: 'studio.7f3a-01:retry'})
        self.assertEqual(response.json(), {'request_id': 'studio.7f3a-01:retry'})
        self.assertEqual(response.headers[REQUEST_ID_HEADER], 'studio.7f3a-01:retry')
        self.assertIsNone(current_request_id())

    def test_an_invalid_client_request_id_is_replaced(self):
        for value in ('', 'has space', 'x' * 129, 'line\tbreak', '-leading', 'ünï'):
            with self.subTest(value=value):
                response = self.client.get('/fail/request-id', headers={REQUEST_ID_HEADER: value.encode('utf-8')})
                generated = response.headers[REQUEST_ID_HEADER]
                self.assertTrue(re.fullmatch(r'[0-9a-f]{32}', generated), generated)
                self.assertEqual(response.json(), {'request_id': generated})


class ModuleRegistryTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)

    def test_duplicate_module_names_are_refused(self):
        with self.assertRaises(ConfigurationError):
            ModuleRegistry((module('review', '/a'), module('review', '/b')))

    def test_selection_by_configuration(self):
        registry = ModuleRegistry((module('review', '/review'), module('projects', '/projects')))
        self.assertEqual(registry.names, ('review', 'projects'))
        self.assertEqual([m.name for m in registry.select(None)], ['review', 'projects'])
        self.assertEqual([m.name for m in registry.select(['projects'])], ['projects'])
        self.assertEqual(registry.select([]), ())
        with self.assertRaises(ConfigurationError):
            registry.select(['review', 'unknown'])

    def test_a_module_that_is_off_has_no_routes(self):
        registry = ModuleRegistry((module('review', '/review'), module('projects', '/projects')))
        client = api_client(FakeProvider(), registry.select(['projects']))
        self.assertEqual(client.get('/projects').json(), {'module': 'projects'})
        self.assertEqual(client.get('/review').status_code, 404)

    def test_write_routes_must_require_the_csrf_check(self):
        router = APIRouter()
        router.add_api_route('/unprotected', lambda: None, methods=['POST'])
        with self.assertRaisesRegex(ConfigurationError, 'POST /unprotected'):
            api_client(FakeProvider(), (ApiModule('unsafe', router),))
        protected = APIRouter(dependencies=[Depends(csrf_protected)])
        protected.add_api_route('/protected', lambda: None, methods=['PUT', 'DELETE', 'PATCH'])
        api_client(FakeProvider(), (ApiModule('safe', protected),))

    def test_module_routers_declare_their_routes_directly(self):
        outer, inner = APIRouter(), APIRouter()
        inner.add_api_route('/hidden', lambda: None, methods=['POST'])
        outer.include_router(inner)
        with self.assertRaisesRegex(ConfigurationError, 'nested'):
            api_client(FakeProvider(), (ApiModule('nested', outer),))


class SettingsTest(unittest.TestCase):
    ENV = {'ALM_OIDC_ISSUER': 'http://127.0.0.1:58080/realms/alm-dev', 'ALM_OIDC_CLIENT_ID': 'alm-authoring-api',
           'ALM_OIDC_CLIENT_SECRET': 'secret-value', 'ALM_OIDC_REDIRECT_URI': 'http://127.0.0.1:58000/auth/callback',
           'ALM_IDENTITY_MAP': 'identity-map.json'}

    def test_reads_the_environment_without_exposing_the_secret(self):
        settings = ApiSettings.from_env({**self.ENV, 'ALM_API_COOKIE_SECURE': 'false', 'ALM_API_SESSION_TTL': '900'})
        self.assertFalse(settings.auth.cookie_secure)
        self.assertEqual(settings.auth.session_ttl, 900)
        self.assertEqual(settings.auth.client_secret.get_secret_value(), 'secret-value')
        self.assertNotIn('secret-value', repr(settings))
        self.assertIsNone(settings.modules)
        self.assertIsNone(settings.auth.post_logout_redirect_uri)
        self.assertEqual(ApiSettings.from_env({**self.ENV, 'ALM_API_MODULES': ''}).modules, ())
        self.assertEqual(ApiSettings.from_env({**self.ENV, 'ALM_API_MODULES': 'review, projects'}).modules,
                         ('review', 'projects'))

    def test_missing_settings_are_named(self):
        with self.assertRaisesRegex(ValueError, 'ALM_OIDC_CLIENT_SECRET, ALM_IDENTITY_MAP'):
            ApiSettings.from_env({k: v for k, v in self.ENV.items()
                                  if k not in ('ALM_OIDC_CLIENT_SECRET', 'ALM_IDENTITY_MAP')})
        with self.assertRaises(ValueError):
            ApiSettings.from_env({**self.ENV, 'ALM_API_SESSION_TTL': '0'})


if __name__ == '__main__':
    unittest.main()
