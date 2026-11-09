"""Login, callback, session and logout routes, and the dependencies modules use (D8, D9).

Modules depend on :func:`current_principal` to read and on :func:`csrf_protected`
to write. A principal carries only the policy ``subject_key``; the trusted
policy decides what it may do.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import secrets
import time
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import httpx

from services.api_common.identity import IdentityMap
from services.api_common.oidc import LoginFailed, OidcClient, ProviderUnavailable, new_secret, pkce_pair
from services.api_common.registry import ApiModule
from services.api_common.sessions import MemorySessionStore, PendingLogin, Session
from services.api_common.settings import AuthSettings


SESSION_COOKIE = 'alm_session'
LOGIN_COOKIE = 'alm_login'
CSRF_HEADER = 'X-CSRF-Token'
logger = logging.getLogger('services.api_common')


@dataclass(frozen=True)
class Principal:
    subject_key: str


class SessionView(BaseModel):
    subject_key: str
    csrf_token: str
    expires_at: datetime


class LogoutView(BaseModel):
    end_session_url: str | None


def local_path(value: str | None) -> str:
    """Only a path on this site; anything that could leave it becomes ``/``."""
    if not value or not value.startswith('/') or value.startswith('//') or '\\' in value:
        return '/'
    return value


class Authenticator:
    def __init__(self, settings: AuthSettings, identities: IdentityMap, *,
                 transport: httpx.BaseTransport | None = None, clock: Callable[[], float] = time.time,
                 sessions: MemorySessionStore | None = None):
        self.settings = settings
        self.identities = identities
        self.oidc = OidcClient(settings, transport=transport)
        self.clock = clock
        self.sessions = sessions or MemorySessionStore()

    def _set_cookie(self, response: Response, name: str, value: str, max_age: int, path: str) -> None:
        response.set_cookie(name, value, max_age=max_age, path=path, httponly=True,
                            secure=self.settings.cookie_secure, samesite='lax')

    def _clear_cookie(self, response: Response, name: str, path: str) -> None:
        response.delete_cookie(name, path=path, httponly=True, secure=self.settings.cookie_secure, samesite='lax')

    def login(self, return_to: str | None) -> Response:
        state, nonce = new_secret(), new_secret()
        verifier, challenge = pkce_pair()
        url = self.oidc.authorization_url(state, nonce, challenge)
        now = self.clock()
        self.sessions.begin_login(PendingLogin(state, nonce, verifier, local_path(return_to),
                                               now + self.settings.login_ttl), now)
        response = RedirectResponse(url, status_code=302)
        self._set_cookie(response, LOGIN_COOKIE, state, self.settings.login_ttl, '/auth')
        return response

    def callback(self, request: Request, state: str | None, code: str | None, error: str | None) -> Response:
        bound = request.cookies.get(LOGIN_COOKIE)
        if not state or not bound or not secrets.compare_digest(bound, state):
            raise HTTPException(401, 'Login failed')
        login = self.sessions.finish_login(state, self.clock())
        if login is None or error or not code:
            raise HTTPException(401, 'Login failed')
        try:
            tokens = self.oidc.exchange(code, login.code_verifier)
            claims = self.oidc.verify_id_token(tokens.id_token, login.nonce)
        except LoginFailed as failure:
            logger.warning('Login refused: %s', failure)
            raise HTTPException(401, 'Login failed') from None
        if self.identities.subject_key(claims['iss'], claims['sub']) is None:
            logger.warning('Login refused: identity is not mapped')
            raise HTTPException(403, 'Identity is not mapped to a policy subject')
        now = self.clock()
        session = Session(new_secret(), claims['iss'], claims['sub'], new_secret(), tokens.id_token,
                          tokens.access_token, tokens.refresh_token, now + self.settings.session_ttl)
        self.sessions.create(session, now)
        response = RedirectResponse(login.return_to, status_code=303)
        self._set_cookie(response, SESSION_COOKIE, session.id, self.settings.session_ttl, '/')
        self._clear_cookie(response, LOGIN_COOKIE, '/auth')
        return response

    def session(self, request: Request) -> Session:
        session_id = request.cookies.get(SESSION_COOKIE)
        session = self.sessions.get(session_id, self.clock()) if session_id else None
        if session is None:
            raise HTTPException(401, 'Authentication required')
        return session

    def principal(self, session: Session) -> Principal:
        subject_key = self.identities.subject_key(session.issuer, session.subject)
        if subject_key is None:
            raise HTTPException(403, 'Identity is not mapped to a policy subject')
        return Principal(subject_key)

    def logout(self, request: Request, response: Response) -> str | None:
        session = self.session(request)
        self.sessions.delete(session.id)
        self._clear_cookie(response, SESSION_COOKIE, '/')
        return self.oidc.end_session_url(session.id_token)


def authenticator(request: Request) -> Authenticator:
    return request.app.state.authenticator


def current_principal(request: Request) -> Principal:
    auth = authenticator(request)
    return auth.principal(auth.session(request))


def csrf_protected(request: Request) -> Principal:
    """The principal of a write: the session's CSRF token must be in ``X-CSRF-Token``."""
    auth = authenticator(request)
    session = auth.session(request)
    principal = auth.principal(session)
    supplied = request.headers.get(CSRF_HEADER, '')
    if not secrets.compare_digest(supplied.encode(), session.csrf_token.encode()):
        raise HTTPException(403, 'CSRF token missing or invalid')
    return principal


router = APIRouter(prefix='/auth', tags=['auth'])


@router.get('/login', status_code=302, response_class=RedirectResponse,
            summary='Start the OIDC code flow with PKCE at the identity provider')
def login(request: Request, return_to: str | None = Query(None, description='Local path to return to')):
    try:
        return authenticator(request).login(return_to)
    except ProviderUnavailable as failure:
        logger.warning('Login not started: %s', failure)
        raise HTTPException(502, 'Identity provider unavailable') from None


@router.get('/callback', status_code=303, response_class=RedirectResponse,
            summary='Finish the code flow, map the identity and start a server-side session')
def callback(request: Request, state: str | None = None, code: str | None = None, error: str | None = None):
    try:
        return authenticator(request).callback(request, state, code, error)
    except ProviderUnavailable as failure:
        logger.warning('Login not finished: %s', failure)
        raise HTTPException(502, 'Identity provider unavailable') from None


@router.get('/session', response_model=SessionView, summary='The signed-in subject and the CSRF token for writes')
def session(request: Request, response: Response):
    auth = authenticator(request)
    current = auth.session(request)
    principal = auth.principal(current)
    response.headers['Cache-Control'] = 'no-store'
    return SessionView(subject_key=principal.subject_key, csrf_token=current.csrf_token,
                       expires_at=datetime.fromtimestamp(current.expires_at, timezone.utc))


@router.post('/logout', response_model=LogoutView,
             summary='End the session; the result is the provider logout URL to visit, if any')
def logout(request: Request, response: Response, _: Principal = Depends(csrf_protected)):
    return LogoutView(end_session_url=authenticator(request).logout(request, response))


MODULE = ApiModule('auth', router)
