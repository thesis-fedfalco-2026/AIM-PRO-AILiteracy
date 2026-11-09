"""Authoring API app: the shared skeleton plus the authoring modules selected by configuration."""

from __future__ import annotations

import httpx
from fastapi import FastAPI

from services.api_common.app import create_app as build_app
from services.api_common.auth import Authenticator
from services.api_common.identity import IdentityMap, load_identity_map
from services.api_common.registry import ModuleRegistry
from services.api_common.settings import ApiSettings, AuthSettings


TITLE = 'ALM Authoring API'
VERSION = '0.1.0'
REGISTRY = ModuleRegistry(())


def create_app(settings: ApiSettings | None = None, *, transport: httpx.BaseTransport | None = None) -> FastAPI:
    settings = settings or ApiSettings.from_env()
    authenticator = Authenticator(settings.auth, load_identity_map(settings.identity_map), transport=transport)
    return build_app(TITLE, VERSION, REGISTRY.select(settings.modules), authenticator)


def schema_app() -> FastAPI:
    """Every registered module with placeholder settings: the contract, not a deployment."""
    settings = AuthSettings(issuer='https://identity.invalid', client_id='schema', client_secret='unused',
                            redirect_uri='https://api.invalid/auth/callback')
    return build_app(TITLE, VERSION, REGISTRY.select(None),
                     Authenticator(settings, IdentityMap(format=1, identities=())))
