"""API settings read from the host environment; secrets never come from the repository."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from learning.contracts import Text


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, hide_input_in_errors=True)


class AuthSettings(Settings):
    """OIDC code flow of the backend-for-frontend (D8): a confidential client with PKCE."""
    issuer: Text
    client_id: Text
    client_secret: SecretStr
    redirect_uri: Text
    post_logout_redirect_uri: Text | None = None
    cookie_secure: bool = True
    session_ttl: int = Field(3600, gt=0, description='Session lifetime in seconds')
    login_ttl: int = Field(600, gt=0, description='Seconds a started login may take to return')


class ApiSettings(Settings):
    auth: AuthSettings
    identity_map: Path
    modules: tuple[Text, ...] | None = None

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> ApiSettings:
        """Read ``ALM_OIDC_*``, ``ALM_IDENTITY_MAP`` and ``ALM_API_*``; unset ``ALM_API_MODULES`` selects all modules."""
        env = os.environ if environ is None else environ
        missing = [name for name in ('ALM_OIDC_ISSUER', 'ALM_OIDC_CLIENT_ID', 'ALM_OIDC_CLIENT_SECRET',
                                     'ALM_OIDC_REDIRECT_URI', 'ALM_IDENTITY_MAP') if not env.get(name)]
        if missing:
            raise ValueError('Missing API settings: ' + ', '.join(missing))
        auth = {'issuer': env['ALM_OIDC_ISSUER'], 'client_id': env['ALM_OIDC_CLIENT_ID'],
                'client_secret': env['ALM_OIDC_CLIENT_SECRET'], 'redirect_uri': env['ALM_OIDC_REDIRECT_URI'],
                'post_logout_redirect_uri': env.get('ALM_OIDC_POST_LOGOUT_REDIRECT_URI') or None}
        for name, field in (('ALM_API_COOKIE_SECURE', 'cookie_secure'), ('ALM_API_SESSION_TTL', 'session_ttl'),
                            ('ALM_API_LOGIN_TTL', 'login_ttl')):
            if env.get(name):
                auth[field] = env[name]
        modules = env.get('ALM_API_MODULES')
        return cls(auth=auth, identity_map=Path(env['ALM_IDENTITY_MAP']),
                   modules=None if modules is None else tuple(m.strip() for m in modules.split(',') if m.strip()))
