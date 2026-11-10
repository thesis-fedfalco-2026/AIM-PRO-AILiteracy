"""Authoring API app: the shared skeleton plus the authoring modules selected by configuration."""

from __future__ import annotations

import httpx
from fastapi import FastAPI

from services.api_common.app import create_app as build_app
from services.api_common.auth import Authenticator
from services.api_common.contexts import ContextServices, PolicyDirectory
from services.api_common.identity import IdentityMap, load_identity_map
from services.api_common.registry import ConfigurationError, ModuleRegistry
from services.api_common.settings import ApiSettings, AuthSettings
from services.authoring_api import context_summary, courses, exports, jobs, projects, releases, review, sources, syllabus


TITLE = 'ALM Authoring API'
VERSION = '0.7.0'
REGISTRY = ModuleRegistry((context_summary.MODULE, review.MODULE, projects.MODULE, releases.MODULE, jobs.MODULE,
                           courses.MODULE, exports.MODULE, sources.MODULE, syllabus.MODULE))


def create_app(settings: ApiSettings | None = None, *, transport: httpx.BaseTransport | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    modules = REGISTRY.select(settings.modules)
    contexts = None
    if modules:
        # Every authoring module reads contexts; identity-only deployments select no module.
        if settings.store is None or settings.policy_dir is None:
            raise ConfigurationError('Authoring modules need ALM_STORE and ALM_POLICY_DIR')
        contexts = ContextServices(settings.store.get_secret_value(), PolicyDirectory(settings.policy_dir))
    if jobs.MODULE in modules and settings.jobs_store is None:
        raise ConfigurationError('The jobs module needs ALM_JOBS_STORE')
    if courses.MODULE in modules:
        if settings.course_template is None:
            raise ConfigurationError('The courses module needs ALM_COURSE_TEMPLATE')
        courses.load_template(settings.course_template)
    if exports.MODULE in modules and (settings.aimpro_exports is None or not settings.aimpro_exports.is_dir()):
        raise ConfigurationError('The exports module needs ALM_AIMPRO_EXPORTS, an existing directory')
    authenticator = Authenticator(settings.auth, load_identity_map(settings.identity_map), transport=transport)
    app = build_app(TITLE, VERSION, modules, authenticator)
    app.state.contexts = contexts
    jobs.configure(app, settings)
    courses.configure(app, settings)
    exports.configure(app, settings)
    return app


def schema_app() -> FastAPI:
    """Every registered module with placeholder settings: the contract, not a deployment."""
    settings = AuthSettings(issuer='https://identity.invalid', client_id='schema', client_secret='unused',
                            redirect_uri='https://api.invalid/auth/callback')
    return build_app(TITLE, VERSION, REGISTRY.select(None),
                     Authenticator(settings, IdentityMap(format=1, identities=())))
