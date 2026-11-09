"""One error shape for every API: ``{"error", "detail", "request_id"}``.

``StateConflict`` → 409 (reload and retry), ``AuthorizationError`` → 403,
``ContextUnavailable`` → 404, validation (request models, records, core
``ValueError``) → 422, anything else → 500 without detail. Validation errors
never echo input values, which may be private text. :func:`error_responses`
documents the same body in the OpenAPI snapshot.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.exceptions import HTTPException

from learning.policies import AuthorizationError
from learning.store import StateConflict
from services.api_common.request_ids import REQUEST_ID_HEADER, accepted_request_id


logger = logging.getLogger('services.api_common')

CODES = {400: 'bad_request', 401: 'unauthenticated', 403: 'forbidden', 404: 'not_found',
         405: 'method_not_allowed', 409: 'conflict', 422: 'validation', 500: 'internal',
         502: 'identity_provider_unavailable'}


class ContextUnavailable(Exception):
    """The context does not exist or its trusted policy is not installed; ``reason`` is only logged."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__('Context unavailable')


DESCRIPTIONS = {401: 'No valid session', 403: 'Not authorized, unmapped identity or missing CSRF token',
                404: 'Not found, or the context is unavailable', 409: 'Conflict with the current state; reload and retry',
                422: 'Invalid request or data', 500: 'Internal error', 502: 'Identity provider unavailable'}


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorBody(BaseModel):
    error: str
    detail: str | list[ValidationIssue]
    request_id: str


def error_responses(*statuses: int) -> dict:
    """OpenAPI ``responses`` for these statuses, all with :class:`ErrorBody`."""
    return {status: {'model': ErrorBody, 'description': DESCRIPTIONS[status]} for status in statuses}


def request_id(request: Request) -> str:
    return getattr(request.state, 'request_id', None) or accepted_request_id(None)


def error_response(request: Request, status: int, detail, headers=None, error: str | None = None) -> JSONResponse:
    rid = request_id(request)
    body = ErrorBody(error=error or CODES.get(status, 'http_error'), detail=detail, request_id=rid)
    return JSONResponse(body.model_dump(), status_code=status, headers={**(headers or {}), REQUEST_ID_HEADER: rid})


def validation_detail(errors) -> list[dict]:
    return [{'loc': list(item['loc']), 'msg': item['msg'], 'type': item['type']} for item in errors]


async def _http(request, error: HTTPException):
    return error_response(request, error.status_code, error.detail, getattr(error, 'headers', None))


async def _conflict(request, error: StateConflict):
    return error_response(request, 409, str(error))


async def _unavailable(request, error: ContextUnavailable):
    logger.warning('Context unavailable (request %s): %s', request_id(request), error.reason)
    return error_response(request, 404, str(error), error='context_unavailable')


async def _forbidden(request, error: AuthorizationError):
    return error_response(request, 403, 'Action is not authorized')


async def _request_validation(request, error: RequestValidationError):
    return error_response(request, 422, validation_detail(error.errors()))


async def _record_validation(request, error: ValidationError):
    return error_response(request, 422, validation_detail(error.errors(include_url=False, include_input=False)))


async def _invalid(request, error: ValueError):
    return error_response(request, 422, str(error))


async def _internal(request, error: Exception):
    logger.error('Unhandled API error (request %s)', request_id(request), exc_info=error)
    return error_response(request, 500, 'Internal error')


def install_error_handlers(app: FastAPI) -> None:
    """Handlers resolve by class hierarchy, so the most specific mapping wins."""
    app.add_exception_handler(HTTPException, _http)
    app.add_exception_handler(StateConflict, _conflict)
    app.add_exception_handler(AuthorizationError, _forbidden)
    app.add_exception_handler(ContextUnavailable, _unavailable)
    app.add_exception_handler(RequestValidationError, _request_validation)
    app.add_exception_handler(ValidationError, _record_validation)
    app.add_exception_handler(ValueError, _invalid)
    app.add_exception_handler(Exception, _internal)
