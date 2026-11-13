"""Bound each LLM HTTP request by wall-clock time, not only by socket read.

httpx timeouts apply to each read, so a provider that sends keep-alive bytes
(OpenRouter does while a model is queued or thinking) can hold one request open
indefinitely. The interceptor fails the response body once the deadline passes.
"""

from contextvars import ContextVar
import time

import httpx
from crewai.llms.hooks.base import BaseInterceptor

# Transports call on_outbound and on_inbound in sequence in one thread or task,
# before httpx attaches the request to the response.
_pending: ContextVar[tuple[httpx.Request, float]] = ContextVar("llm_request_deadline")


class DeadlineExceeded(httpx.ReadTimeout):
    """An LLM request that reached its wall-clock deadline; callers name it with their own fixed text."""


def expired(request: httpx.Request, seconds: float) -> DeadlineExceeded:
    return DeadlineExceeded(f"LLM request exceeded its {seconds:g}s wall-clock deadline", request=request)


def _caused_by(error: BaseException, kind) -> bool:
    seen = set()
    while error is not None and id(error) not in seen:
        if isinstance(error, kind):
            return True
        seen.add(id(error))
        error = error.__cause__ or error.__context__
    return False


def reached(error: BaseException) -> bool:
    """Whether ``error`` is, or was raised while handling, a request past its deadline (SDKs wrap it)."""
    return _caused_by(error, DeadlineExceeded)


def cut(error: BaseException) -> bool:
    """Whether ``error`` comes from a response the provider cut at its output length limit."""
    from openai import LengthFinishReasonError
    return _caused_by(error, LengthFinishReasonError)


class _DeadlineStream(httpx.SyncByteStream):
    def __init__(self, stream, request, deadline, seconds):
        self._stream, self._request, self._deadline, self._seconds = stream, request, deadline, seconds

    def __iter__(self):
        for chunk in self._stream:
            if time.monotonic() > self._deadline:
                raise expired(self._request, self._seconds)
            yield chunk

    def close(self):
        self._stream.close()


class _AsyncDeadlineStream(httpx.AsyncByteStream):
    def __init__(self, stream, request, deadline, seconds):
        self._stream, self._request, self._deadline, self._seconds = stream, request, deadline, seconds

    async def __aiter__(self):
        async for chunk in self._stream:
            if time.monotonic() > self._deadline:
                raise expired(self._request, self._seconds)
            yield chunk

    async def aclose(self):
        await self._stream.aclose()


class RequestDeadline(BaseInterceptor[httpx.Request, httpx.Response]):
    """Each HTTP attempt gets its own deadline; SDK retries start a new one."""

    def __init__(self, seconds: float):
        self.seconds = seconds

    def __eq__(self, other):
        return isinstance(other, RequestDeadline) and other.seconds == self.seconds

    def on_outbound(self, message: httpx.Request) -> httpx.Request:
        _pending.set((message, time.monotonic() + self.seconds))
        return message

    def on_inbound(self, message: httpx.Response) -> httpx.Response:
        message.stream = _DeadlineStream(message.stream, *_pending.get(), self.seconds)
        return message

    async def aon_outbound(self, message: httpx.Request) -> httpx.Request:
        return self.on_outbound(message)

    async def aon_inbound(self, message: httpx.Response) -> httpx.Response:
        message.stream = _AsyncDeadlineStream(message.stream, *_pending.get(), self.seconds)
        return message
