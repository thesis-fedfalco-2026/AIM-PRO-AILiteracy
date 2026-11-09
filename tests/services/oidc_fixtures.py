"""An in-memory OpenID provider for API tests: local key pair, JWKS and token endpoint.

The provider answers through ``httpx.MockTransport``, so no request leaves the
process. Identities and keys are generated per test; nothing here is a real
account or credential.
"""

from base64 import urlsafe_b64encode
from hashlib import sha256
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from fastapi.testclient import TestClient

from services.api_common.app import create_app
from services.api_common.auth import Authenticator
from services.api_common.identity import IdentityMap
from services.api_common.settings import AuthSettings


ISSUER = 'https://idp.test/realms/alm'
CLIENT_ID = 'alm-authoring-api'
CLIENT_SECRET = 'test-client-secret'
REDIRECT_URI = 'https://testserver/auth/callback'
POST_LOGOUT_REDIRECT_URI = 'https://testserver/'
MAPPED_SUBJECT = 'kc-user-admin'
UNMAPPED_SUBJECT = 'kc-user-unmapped'
NO_NETWORK = 'API tests use an in-memory identity provider and no network'


def new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def challenge(verifier):
    return urlsafe_b64encode(sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')


def query(url):
    return {name: values[0] for name, values in parse_qs(urlsplit(url).query).items()}


class FakeProvider:
    """Discovery, JWKS and token endpoints of one issuer, with recorded token requests."""

    def __init__(self, issuer=ISSUER):
        self.issuer = issuer
        self.key = new_key()
        self.kid = 'test-key-1'
        self.token_requests = []
        self.discovery_issuer = issuer
        self._codes = {}

    @property
    def transport(self):
        return httpx.MockTransport(self.handle)

    def metadata(self):
        base = self.issuer + '/protocol/openid-connect'
        return {'issuer': self.discovery_issuer, 'authorization_endpoint': base + '/auth',
                'token_endpoint': base + '/token', 'jwks_uri': base + '/certs',
                'end_session_endpoint': base + '/logout',
                'id_token_signing_alg_values_supported': ['RS256']}

    def jwks(self):
        jwk = json.loads(RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update(kid=self.kid, use='sig', alg='RS256')
        return {'keys': [jwk]}

    def claims(self, login_nonce, subject=MAPPED_SUBJECT, **overrides):
        now = int(time.time())
        claims = {'iss': self.issuer, 'sub': subject, 'aud': CLIENT_ID, 'azp': CLIENT_ID,
                  'iat': now, 'exp': now + 300, 'nonce': login_nonce}
        claims.update(overrides)
        return {name: value for name, value in claims.items() if value is not None}

    def sign(self, claims, key=None, kid=None, algorithm='RS256'):
        return jwt.encode(claims, self.key if key is None else key, algorithm=algorithm,
                          headers={'kid': kid or self.kid})

    def issue(self, id_token):
        """Register an authorization code that the token endpoint exchanges for ``id_token``."""
        code = 'code-' + uuid4().hex
        self._codes[code] = id_token
        return code

    def handle(self, request):
        base = self.issuer + '/protocol/openid-connect'
        url = str(request.url)
        if url == self.issuer + '/.well-known/openid-configuration':
            return httpx.Response(200, json=self.metadata())
        if url == base + '/certs':
            return httpx.Response(200, json=self.jwks())
        if url == base + '/token' and request.method == 'POST':
            form = {name: values[0] for name, values in parse_qs(request.content.decode()).items()}
            self.token_requests.append(form)
            id_token = self._codes.pop(form.get('code'), None)
            if id_token is None:
                return httpx.Response(400, json={'error': 'invalid_grant'})
            return httpx.Response(200, json={'id_token': id_token, 'access_token': 'access-' + uuid4().hex,
                                             'refresh_token': 'refresh-' + uuid4().hex,
                                             'token_type': 'Bearer', 'expires_in': 300})
        return httpx.Response(404)


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


def write_identity_map(directory, *entries):
    path = Path(directory) / 'identity-map.json'
    identities = entries or ({'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'},)
    path.write_text(json.dumps({'format': 1, 'identities': list(identities)}), encoding='utf-8')
    return path


def auth_settings(**overrides):
    values = {'issuer': ISSUER, 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
              'redirect_uri': REDIRECT_URI, 'post_logout_redirect_uri': POST_LOGOUT_REDIRECT_URI,
              'session_ttl': 3600, 'login_ttl': 600}
    values.update(overrides)
    return AuthSettings(**values)


def api_client(provider, modules=(), identities=None, clock=None, **settings):
    identities = identities or IdentityMap.model_validate(
        {'format': 1, 'identities': [{'issuer': ISSUER, 'subject': MAPPED_SUBJECT, 'subject_key': 'admin'}]})
    authenticator = Authenticator(auth_settings(**settings), identities,
                                  transport=provider.transport, clock=clock or Clock())
    app = create_app('Test API', '0.0.0', modules, authenticator)
    return TestClient(app, base_url='https://testserver', raise_server_exceptions=False,
                      follow_redirects=False)


def begin_login(client, return_to=None):
    response = client.get('/auth/login', params={} if return_to is None else {'return_to': return_to})
    return response, query(response.headers['location'])


def log_in(client, provider, subject=MAPPED_SUBJECT, return_to=None, **claims):
    """Run the code flow to the callback; the result is the callback response."""
    _, params = begin_login(client, return_to)
    code = provider.issue(provider.sign(provider.claims(params['nonce'], subject, **claims)))
    return client.get('/auth/callback', params={'code': code, 'state': params['state']})
