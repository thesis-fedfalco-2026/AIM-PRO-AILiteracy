"""OIDC login, server-side sessions, CSRF and identity mapping of the API skeleton (S03, D8, D9).

The identity provider is in memory (``oidc_fixtures.FakeProvider``) and the
network is blocked: no test reaches Keycloak or any other service.
"""

from http.cookies import SimpleCookie
import json
from tempfile import TemporaryDirectory
import unittest

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from services.api_common.auth import (CSRF_HEADER, LOGIN_COOKIE, SESSION_COOKIE, Principal,
                                      csrf_protected, current_principal)
from services.api_common.identity import IdentityMap, load_identity_map
from services.api_common.registry import ApiModule
from tests.services.oidc_fixtures import (CLIENT_ID, CLIENT_SECRET, ISSUER, MAPPED_SUBJECT,
                                          NO_NETWORK, POST_LOGOUT_REDIRECT_URI, REDIRECT_URI,
                                          UNMAPPED_SUBJECT, Clock, FakeProvider, api_client,
                                          begin_login, challenge, log_in, new_key, query,
                                          write_identity_map)
from tests.store_backends import block_network


def set_cookies(response):
    cookies = SimpleCookie()
    for header in response.headers.get_list('set-cookie'):
        cookies.load(header)
    return cookies


def probe_module():
    router = APIRouter()

    @router.get('/probe')
    def read(principal: Principal = Depends(current_principal)):
        return {'subject_key': principal.subject_key}

    @router.post('/probe')
    def write(principal: Principal = Depends(csrf_protected)):
        return {'written_by': principal.subject_key}

    return ApiModule('probe', router)


class LoginTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        self.provider = FakeProvider()
        self.clock = Clock()
        self.client = api_client(self.provider, (probe_module(),), clock=self.clock)

    def assert_refused(self, response, status, error):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()['error'], error)
        self.assertNotIn(SESSION_COOKIE, set_cookies(response))

    def test_login_redirects_to_the_provider_with_pkce_state_and_nonce(self):
        response, params = begin_login(self.client)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['location'].startswith(ISSUER + '/protocol/openid-connect/auth?'))
        self.assertEqual(params['response_type'], 'code')
        self.assertEqual(params['client_id'], CLIENT_ID)
        self.assertEqual(params['redirect_uri'], REDIRECT_URI)
        self.assertEqual(params['scope'], 'openid')
        self.assertEqual(params['code_challenge_method'], 'S256')
        self.assertGreaterEqual(len(params['state']), 32)
        self.assertGreaterEqual(len(params['nonce']), 32)
        self.assertNotEqual(params['state'], params['nonce'])
        self.assertNotIn('code_verifier', params)
        cookies = set_cookies(response)
        self.assertEqual(cookies[LOGIN_COOKIE].value, params['state'])
        self.assertTrue(cookies[LOGIN_COOKIE]['httponly'])
        self.assertTrue(cookies[LOGIN_COOKIE]['secure'])
        self.assertEqual(cookies[LOGIN_COOKIE]['samesite'], 'lax')
        self.assertEqual(cookies[LOGIN_COOKIE]['path'], '/auth')
        self.assertNotIn(SESSION_COOKIE, cookies)
        self.assertEqual(self.provider.token_requests, [])

    def test_callback_exchanges_the_code_with_the_verifier_and_sets_a_session_cookie(self):
        _, params = begin_login(self.client)
        code = self.provider.issue(self.provider.sign(self.provider.claims(params['nonce'])))
        response = self.client.get('/auth/callback', params={'code': code, 'state': params['state']})
        self.assertEqual(response.status_code, 303, response.text)
        self.assertEqual(response.headers['location'], '/')
        [token_request] = self.provider.token_requests
        self.assertEqual(token_request['grant_type'], 'authorization_code')
        self.assertEqual(token_request['code'], code)
        self.assertEqual(token_request['redirect_uri'], REDIRECT_URI)
        self.assertEqual(token_request['client_id'], CLIENT_ID)
        self.assertEqual(token_request['client_secret'], CLIENT_SECRET)
        self.assertEqual(challenge(token_request['code_verifier']), params['code_challenge'])
        cookie = set_cookies(response)[SESSION_COOKIE]
        self.assertGreaterEqual(len(cookie.value), 32)
        self.assertTrue(cookie['httponly'])
        self.assertTrue(cookie['secure'])
        self.assertEqual(cookie['samesite'], 'lax')
        self.assertEqual(cookie['path'], '/')
        self.assertEqual(set_cookies(response)[LOGIN_COOKIE]['max-age'], '0')

    def test_session_reports_the_mapped_subject_and_never_the_tokens(self):
        self.assertEqual(log_in(self.client, self.provider).status_code, 303)
        response = self.client.get('/auth/session')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        body = response.json()
        self.assertEqual(set(body), {'subject_key', 'csrf_token', 'expires_at'})
        self.assertEqual(body['subject_key'], 'admin')
        self.assertGreaterEqual(len(body['csrf_token']), 32)
        self.assertNotIn('access-', response.text)
        self.assertNotIn('refresh-', response.text)
        self.assertNotIn(MAPPED_SUBJECT, response.text)
        self.assertEqual(self.client.get('/probe').json(), {'subject_key': 'admin'})

    def test_return_path_is_kept_only_when_it_is_local(self):
        for requested, expected in (('/studio/inbox?tab=pending', '/studio/inbox?tab=pending'),
                                    ('https://elsewhere.test/', '/'), ('//elsewhere.test/x', '/'),
                                    ('/\\elsewhere.test', '/'), ('studio', '/')):
            with self.subTest(requested=requested):
                response = log_in(self.client, self.provider, return_to=requested)
                self.assertEqual(response.headers['location'], expected)

    def test_requests_without_a_session_are_unauthenticated(self):
        for path in ('/auth/session', '/probe'):
            with self.subTest(path=path):
                self.assert_refused(self.client.get(path), 401, 'unauthenticated')
        self.client.cookies.set(SESSION_COOKIE, 'forged-session-id')
        self.assert_refused(self.client.get('/auth/session'), 401, 'unauthenticated')

    def test_session_expires_after_its_lifetime(self):
        log_in(self.client, self.provider)
        self.clock.now += 3599
        self.assertEqual(self.client.get('/auth/session').status_code, 200)
        self.clock.now += 1
        self.assert_refused(self.client.get('/auth/session'), 401, 'unauthenticated')
        self.clock.now -= 10
        self.assert_refused(self.client.get('/auth/session'), 401, 'unauthenticated')

    def test_unmapped_identity_is_forbidden_and_gets_no_session(self):
        response = log_in(self.client, self.provider, subject=UNMAPPED_SUBJECT)
        self.assert_refused(response, 403, 'forbidden')
        self.assertNotIn(UNMAPPED_SUBJECT, response.text)
        self.assert_refused(self.client.get('/auth/session'), 401, 'unauthenticated')

    def test_same_subject_from_another_issuer_is_not_mapped(self):
        other = FakeProvider('https://other-idp.test/realms/alm')
        client = api_client(other, clock=self.clock, issuer=other.issuer)
        self.assert_refused(log_in(client, other), 403, 'forbidden')

    def test_invalid_id_tokens_are_refused(self):
        foreign = new_key()
        cases = {
            'expired': {'claims': {'iat': 1, 'exp': 2}},
            'foreign issuer': {'claims': {'iss': 'https://other-idp.test/realms/alm'}},
            'other audience': {'claims': {'aud': 'another-client', 'azp': 'another-client'}},
            'extra audience without azp': {'claims': {'aud': [CLIENT_ID, 'another-client'], 'azp': 'another-client'}},
            'nonce mismatch': {'claims': {'nonce': 'not-the-login-nonce'}},
            'missing nonce': {'claims': {'nonce': None}},
            'missing expiry': {'claims': {'exp': None}},
            'foreign key with known kid': {'key': foreign},
            'foreign key with unknown kid': {'key': foreign, 'kid': 'unknown-key'},
            'symmetric algorithm': {'key': b'shared-secret-of-at-least-32-bytes!!', 'algorithm': 'HS256'},
        }
        for name, case in cases.items():
            with self.subTest(name):
                _, params = begin_login(self.client)
                claims = self.provider.claims(params['nonce'], **case.get('claims', {}))
                token = self.provider.sign(claims, case.get('key'), case.get('kid'), case.get('algorithm', 'RS256'))
                response = self.client.get('/auth/callback',
                                           params={'code': self.provider.issue(token), 'state': params['state']})
                self.assert_refused(response, 401, 'unauthenticated')
                self.assertEqual(response.json()['detail'], 'Login failed')
                self.assert_refused(self.client.get('/auth/session'), 401, 'unauthenticated')

    def test_unsigned_id_token_is_refused(self):
        _, params = begin_login(self.client)
        token = self.provider.sign(self.provider.claims(params['nonce']), algorithm='none', key='')
        response = self.client.get('/auth/callback',
                                   params={'code': self.provider.issue(token), 'state': params['state']})
        self.assert_refused(response, 401, 'unauthenticated')

    def test_state_must_match_the_browser_and_is_used_once(self):
        _, params = begin_login(self.client)
        code = self.provider.issue(self.provider.sign(self.provider.claims(params['nonce'])))
        _, other = begin_login(self.client)
        self.assert_refused(self.client.get('/auth/callback', params={'code': code, 'state': params['state']}),
                            401, 'unauthenticated')
        self.client.cookies.clear()
        self.assert_refused(self.client.get('/auth/callback', params={'code': code, 'state': other['state']}),
                            401, 'unauthenticated')
        self.assertEqual(self.provider.token_requests, [])

        _, params = begin_login(self.client)
        code = self.provider.issue(self.provider.sign(self.provider.claims(params['nonce'])))
        self.assertEqual(self.client.get('/auth/callback', params={'code': code, 'state': params['state']}).status_code, 303)
        self.client.cookies.set(LOGIN_COOKIE, params['state'], path='/auth')
        replay = self.client.get('/auth/callback', params={'code': code, 'state': params['state']})
        self.assert_refused(replay, 401, 'unauthenticated')
        self.assertEqual(len(self.provider.token_requests), 1)

    def test_pending_login_expires(self):
        _, params = begin_login(self.client)
        code = self.provider.issue(self.provider.sign(self.provider.claims(params['nonce'])))
        self.clock.now += 601
        self.assert_refused(self.client.get('/auth/callback', params={'code': code, 'state': params['state']}),
                            401, 'unauthenticated')
        self.assertEqual(self.provider.token_requests, [])

    def test_provider_error_and_refused_code_are_login_failures(self):
        _, params = begin_login(self.client)
        self.assert_refused(self.client.get('/auth/callback', params={'error': 'access_denied', 'state': params['state']}),
                            401, 'unauthenticated')
        _, params = begin_login(self.client)
        self.assert_refused(self.client.get('/auth/callback', params={'code': 'unknown-code', 'state': params['state']}),
                            401, 'unauthenticated')

    def test_discovery_with_another_issuer_is_refused(self):
        self.provider.discovery_issuer = 'https://other-idp.test/realms/alm'
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error'], 'identity_provider_unavailable')


class CsrfAndLogoutTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)
        self.provider = FakeProvider()
        self.client = api_client(self.provider, (probe_module(),))
        log_in(self.client, self.provider)
        self.csrf = self.client.get('/auth/session').json()['csrf_token']

    def test_writes_without_the_csrf_header_are_refused(self):
        for headers in ({}, {CSRF_HEADER: ''}, {CSRF_HEADER: 'wrong-token'}):
            with self.subTest(headers=headers):
                for path in ('/probe', '/auth/logout'):
                    response = self.client.post(path, headers=headers)
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertEqual(response.json()['error'], 'forbidden')
        self.assertEqual(self.client.get('/auth/session').status_code, 200)
        self.assertEqual(self.client.post('/probe', headers={CSRF_HEADER: self.csrf}).json(),
                         {'written_by': 'admin'})

    def test_csrf_token_of_another_session_is_refused(self):
        other = api_client(self.provider, (probe_module(),))
        log_in(other, self.provider)
        token = other.get('/auth/session').json()['csrf_token']
        self.assertEqual(self.client.post('/probe', headers={CSRF_HEADER: token}).status_code, 403)

    def test_write_without_a_session_is_unauthenticated(self):
        self.client.cookies.clear()
        response = self.client.post('/probe', headers={CSRF_HEADER: self.csrf})
        self.assertEqual(response.status_code, 401)

    def test_logout_ends_the_session_and_returns_the_provider_logout_url(self):
        response = self.client.post('/auth/logout', headers={CSRF_HEADER: self.csrf})
        self.assertEqual(response.status_code, 200, response.text)
        url = response.json()['end_session_url']
        self.assertTrue(url.startswith(ISSUER + '/protocol/openid-connect/logout?'))
        params = query(url)
        self.assertEqual(params['client_id'], CLIENT_ID)
        self.assertEqual(params['post_logout_redirect_uri'], POST_LOGOUT_REDIRECT_URI)
        self.assertEqual(params['id_token_hint'].count('.'), 2)
        self.assertEqual(set_cookies(response)[SESSION_COOKIE]['max-age'], '0')
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/auth/session').status_code, 401)


class IdentityMapTest(unittest.TestCase):
    def test_loads_the_host_identity_map(self):
        with TemporaryDirectory() as directory:
            identities = load_identity_map(write_identity_map(
                directory, {'issuer': ISSUER, 'subject': 'a', 'subject_key': 'admin'},
                {'issuer': 'https://other-idp.test', 'subject': 'a', 'subject_key': 'learner'}))
        self.assertEqual(identities.subject_key(ISSUER, 'a'), 'admin')
        self.assertEqual(identities.subject_key('https://other-idp.test', 'a'), 'learner')
        self.assertIsNone(identities.subject_key(ISSUER, 'b'))
        self.assertIsNone(identities.subject_key('https://other-idp.test/', 'a'))

    def test_refuses_ambiguous_or_malformed_maps(self):
        entry = {'issuer': ISSUER, 'subject': 'a', 'subject_key': 'admin'}
        for name, document in {
            'duplicate identity': {'format': 1, 'identities': [entry, {**entry, 'subject_key': 'learner'}]},
            'unknown field': {'format': 1, 'identities': [{**entry, 'roles': ['ADMINISTRATOR']}]},
            'unknown format': {'format': 2, 'identities': [entry]},
            'blank subject key': {'format': 1, 'identities': [{**entry, 'subject_key': ' '}]},
        }.items():
            with self.subTest(name):
                with self.assertRaises(ValidationError):
                    IdentityMap.model_validate_json(json.dumps(document))


if __name__ == '__main__':
    unittest.main()
