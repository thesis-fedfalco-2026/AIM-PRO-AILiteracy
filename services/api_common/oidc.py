"""OpenID Connect client of the backend-for-frontend: discovery, code exchange, ID token checks.

Only the API process talks to the provider; the browser never sees a token
(D8). Discovery and keys are fetched on first use and cached, so building the
app needs no network.
"""

from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
import secrets
from threading import Lock
from urllib.parse import urlencode

import httpx
import jwt
from pydantic import BaseModel, ConfigDict, ValidationError

from services.api_common.settings import AuthSettings


ALGORITHMS = ('RS256',)
LEEWAY = 30  # seconds of clock skew accepted on exp and iat


class LoginFailed(Exception):
    """The provider or its response does not authenticate this login; shown as 401."""


class ProviderUnavailable(Exception):
    """The provider cannot be reached or is not the configured issuer; shown as 502."""


class _Document(BaseModel):
    model_config = ConfigDict(extra='ignore', frozen=True)


class ProviderMetadata(_Document):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    end_session_endpoint: str | None = None


class TokenSet(_Document):
    id_token: str
    access_token: str
    token_type: str
    refresh_token: str | None = None
    expires_in: int | None = None


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def pkce_pair() -> tuple[str, str]:
    """A code verifier (RFC 7636: 43–128 characters) and its S256 challenge."""
    verifier = secrets.token_urlsafe(48)
    return verifier, urlsafe_b64encode(sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')


def _with_query(url: str, params: dict) -> str:
    return url + ('&' if '?' in url else '?') + urlencode(params)


class OidcClient:
    def __init__(self, settings: AuthSettings, *, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._http = httpx.Client(transport=transport, timeout=10.0, follow_redirects=False)
        self._lock = Lock()
        self._metadata: ProviderMetadata | None = None
        self._keys: dict[str | None, jwt.PyJWK] | None = None

    def _get(self, url: str) -> dict:
        try:
            response = self._http.get(url, headers={'Accept': 'application/json'})
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ProviderUnavailable('Identity provider request failed') from error

    def metadata(self) -> ProviderMetadata:
        with self._lock:
            if self._metadata is None:
                try:
                    metadata = ProviderMetadata.model_validate(
                        self._get(self.settings.issuer.rstrip('/') + '/.well-known/openid-configuration'))
                except ValidationError as error:
                    raise ProviderUnavailable('Discovery document is incomplete') from error
                if metadata.issuer != self.settings.issuer:
                    raise ProviderUnavailable('Discovery issuer differs from the configured issuer')
                self._metadata = metadata
            return self._metadata

    def authorization_url(self, state: str, nonce: str, code_challenge: str) -> str:
        return _with_query(self.metadata().authorization_endpoint, {
            'response_type': 'code', 'client_id': self.settings.client_id,
            'redirect_uri': self.settings.redirect_uri, 'scope': 'openid', 'state': state, 'nonce': nonce,
            'code_challenge': code_challenge, 'code_challenge_method': 'S256'})

    def exchange(self, code: str, code_verifier: str) -> TokenSet:
        form = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': self.settings.redirect_uri,
                'code_verifier': code_verifier, 'client_id': self.settings.client_id,
                'client_secret': self.settings.client_secret.get_secret_value()}
        try:
            response = self._http.post(self.metadata().token_endpoint, data=form, headers={'Accept': 'application/json'})
        except httpx.HTTPError as error:
            raise ProviderUnavailable('Token request failed') from error
        if response.status_code in (400, 401):
            raise LoginFailed('Token request refused')
        try:
            response.raise_for_status()
            return TokenSet.model_validate(response.json())
        except httpx.HTTPError as error:
            raise ProviderUnavailable('Token request failed') from error
        except ValueError as error:
            raise LoginFailed('Token response is malformed') from error

    def _key(self, kid: str | None) -> jwt.PyJWK:
        jwks_uri = self.metadata().jwks_uri
        for refresh in (False, True):
            with self._lock:
                if self._keys is None or refresh:
                    try:
                        keys = jwt.PyJWKSet.from_dict(self._get(jwks_uri)).keys
                    except jwt.PyJWTError as error:
                        raise ProviderUnavailable('Provider keys are unusable') from error
                    self._keys = {key.key_id: key for key in keys
                                  if key.public_key_use in (None, 'sig') and key.algorithm_name in ALGORITHMS}
                keys = self._keys
            if kid in keys:
                return keys[kid]
            if kid is None and len(keys) == 1:
                return next(iter(keys.values()))
        raise LoginFailed('ID token key is unknown')

    def verify_id_token(self, token: str, nonce: str) -> dict:
        """Signature, issuer, audience, expiry and nonce of an ID token from the token endpoint."""
        try:
            header = jwt.get_unverified_header(token)
            if header.get('alg') not in ALGORITHMS:
                raise LoginFailed('ID token algorithm is not accepted')
            claims = jwt.decode(token, self._key(header.get('kid')), algorithms=list(ALGORITHMS),
                                audience=self.settings.client_id, issuer=self.settings.issuer, leeway=LEEWAY,
                                options={'require': ['iss', 'sub', 'aud', 'exp', 'iat']})
        except jwt.PyJWTError as error:
            raise LoginFailed('ID token is not valid') from error
        audiences = claims['aud'] if isinstance(claims['aud'], list) else [claims['aud']]
        if len(audiences) > 1 and claims.get('azp') != self.settings.client_id:
            raise LoginFailed('ID token is meant for another party')
        if not isinstance(claims.get('nonce'), str) or not secrets.compare_digest(claims['nonce'], nonce):
            raise LoginFailed('ID token nonce does not match the login')
        if not isinstance(claims['sub'], str) or not claims['sub']:
            raise LoginFailed('ID token has no subject')
        return claims

    def end_session_url(self, id_token: str) -> str | None:
        """RP-initiated logout at the provider, or ``None`` when it offers none or is unreachable."""
        try:
            endpoint = self.metadata().end_session_endpoint
        except ProviderUnavailable:
            return None
        if endpoint is None:
            return None
        params = {'client_id': self.settings.client_id, 'id_token_hint': id_token}
        if self.settings.post_logout_redirect_uri:
            params['post_logout_redirect_uri'] = self.settings.post_logout_redirect_uri
        return _with_query(endpoint, params)
