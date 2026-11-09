"""App factory shared by the role-application APIs."""

from __future__ import annotations

from typing import Iterable, Literal

from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

from services.api_common import auth
from services.api_common.auth import Authenticator, csrf_protected
from services.api_common.errors import install_error_handlers
from services.api_common.registry import ApiModule, ConfigurationError
from services.api_common.request_ids import RequestIdMiddleware


WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


class HealthView(BaseModel):
    status: Literal['ok']


def _calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _calls(dependency)


def unprotected_writes(module: ApiModule) -> list[str]:
    """Write routes of a module that do not depend on :func:`csrf_protected`.

    Checked on the module router before inclusion: a module router holds its
    routes directly, so every route can be inspected.
    """
    found = []
    for route in module.router.routes:
        if not isinstance(route, APIRoute):
            raise ConfigurationError(f'API module {module.name} must declare its routes directly')
        found += [f'{method} {route.path}' for method in sorted(route.methods & WRITE_METHODS)
                  if csrf_protected not in set(_calls(route.dependant))]
    return found


def create_app(title: str, version: str, modules: Iterable[ApiModule], authenticator: Authenticator) -> FastAPI:
    app = FastAPI(title=title, version=version)
    app.state.authenticator = authenticator
    install_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)

    @app.get('/health', response_model=HealthView, tags=['health'], summary='Liveness; needs no session')
    def health():
        return HealthView(status='ok')

    for module in (auth.MODULE, *modules):
        unprotected = unprotected_writes(module)
        if unprotected:
            raise ConfigurationError('Write routes without the CSRF check: ' + ', '.join(unprotected))
        app.include_router(module.router)
    return app
