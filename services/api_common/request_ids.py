"""Request ids: accepted from ``X-Request-ID`` when well formed, generated otherwise, echoed back."""

from __future__ import annotations

from contextvars import ContextVar
import re
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders


REQUEST_ID_HEADER = 'X-Request-ID'
_ACCEPTED = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
_current: ContextVar[str | None] = ContextVar('alm_api_request_id', default=None)


def current_request_id() -> str | None:
    """The id of the HTTP request being handled, for logs, events and traces."""
    return _current.get()


def accepted_request_id(value: str | None) -> str:
    return value if value and _ACCEPTED.fullmatch(value) else uuid4().hex


class RequestIdMiddleware:
    """Pure ASGI middleware, so the id is set before and visible in every handler."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = accepted_request_id(Headers(scope=scope).get(REQUEST_ID_HEADER))
        scope.setdefault('state', {})['request_id'] = request_id

        async def send_with_id(message):
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        token = _current.set(request_id)
        try:
            await self.app(scope, receive, send_with_id)
        finally:
            _current.reset(token)
