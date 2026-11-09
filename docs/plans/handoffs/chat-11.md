# Chat 11 handoff — S03 API skeleton and identity

Date: 9 November 2026. Base: `main` at `3371ce3` (PR #77, S02, merged). Step:
**S03** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 0c).
Issue: [#78](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/78).

- Implementation commit: `d9262d8` on branch `feat/s03-api-skeleton-identity`,
  [PR #79](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/79).
- No model call, no live run, synthetic identities only. The only services used
  were a local Keycloak 26.8.1 from `compose.identity.yml` and the API on
  `127.0.0.1`. AIM-PRO/jjodel exports, the ALM metamodel and the store schema are
  unchanged.

## Objective

A FastAPI service skeleton that authenticates users through Keycloak and maps
them to policy subjects, with no business endpoint yet.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `gh pr view 77` | `MERGED` at `2026-11-09T07:54:59Z`, merge commit `3371ce3`; #76 closed |
| `git log --oneline -3` (after `git checkout main && git pull --ff-only`) | `3371ce3` (merge of #77), `1f86510`, `cddf47a` |
| `gh pr list --state open` | none |
| `git status` | clean except the pre-existing untracked `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/` (not touched, not committed) |
| `unittest discover -q`, telemetry disabled | 701 tests, OK, 107 skipped (as in the Chat 10 handoff) |
| `python -m aimpro.generate --check` | OK |
| D8, D9, D11 | confirmed unchanged by the owner in this chat |
| Installed packages | `uvicorn 0.54.0`, `PyJWT 2.15.1`, `cryptography 50.0.2`, `starlette 1.10.0`, `httpx 0.28.1` already present (through `fastmcp`/`mcp`); `fastapi` absent |

No difference from the Chat 10 handoff, apart from PR #77 being merged.

## D11 versions

Every FastAPI release from `0.142.0` (29 September 2026) to `0.162.2` requires
`opentelemetry-api>=1.44.0`; `crewai 1.15.18` requires `opentelemetry-api~=1.42.0`.
A dry run of `uv pip install fastapi` would have replaced `opentelemetry-api
1.42.1` with `1.45.2`. `fastapi==0.141.1` (29 July 2026, `starlette>=0.46.0`,
`pydantic>=2.9.0`) is the last release without that requirement and installs
with no other change. Pinned: `fastapi==0.141.1`, `uvicorn==0.54.0`,
`pyjwt[crypto]==2.15.1`; `httpx==0.28.1` was already pinned.
`uv pip compile requirements.txt --python-version 3.11` resolves `fastapi 0.141.1`,
`starlette 1.10.0`, `opentelemetry-api 1.42.1`, `crewai 1.15.18`.

## Changes

`services/api_common/`:

| File | Content |
| --- | --- |
| `app.py` | `create_app(title, version, modules, authenticator)`: error handlers, request-id middleware, `GET /health`, the `auth` module, the selected modules. Refuses a module write route (`POST`/`PUT`/`PATCH`/`DELETE`) that does not depend on `csrf_protected`, and a module router that includes other routers |
| `registry.py` | `ApiModule(name, router)`, `ModuleRegistry` (duplicates refused; `select(None)` all, unknown names refused), `ConfigurationError` |
| `errors.py` | body `{"error", "detail", "request_id"}`; `StateConflict` 409, `AuthorizationError` 403 (fixed text), `RequestValidationError`/`ValidationError`/`ValueError` 422 (locations and messages, never input values), HTTP errors with their status, anything else 500 `Internal error`, logged with the request id |
| `request_ids.py` | pure ASGI middleware; `X-Request-ID` kept when it matches `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`, otherwise a new `uuid4().hex`; echoed on every response; `current_request_id()` |
| `oidc.py` | discovery on first use (issuer must equal the configured one), authorization URL with S256 PKCE, `state`, `nonce`; code exchange (`client_secret_post`); ID token checks: RS256 only, key from the JWKS by `kid` (one refresh on an unknown `kid`), `iss`, `aud`, `azp` with several audiences, required `exp`/`iat`/`sub`, 30 s leeway, `nonce`; `end_session_url` |
| `sessions.py` | `MemorySessionStore`: pending logins (used once, expiring) and sessions (expiring), process-local |
| `auth.py` | `Authenticator`; `/auth/login`, `/auth/callback`, `/auth/session`, `/auth/logout`; dependencies `current_principal`, `csrf_protected`; `Principal(subject_key)` |
| `identity.py` | `IdentityMap` format 1, exact (issuer, `sub`) → `subject_key`; duplicates and unknown fields refused |
| `settings.py` | `AuthSettings`, `ApiSettings.from_env()` (`ALM_OIDC_*`, `ALM_IDENTITY_MAP`, `ALM_API_*`); the secret is a `SecretStr` |
| `openapi.py` | `python -m services.api_common.openapi [--check] [--output DIR]` |

Other files:

- `services/authoring_api/`: `create_app()` from the environment, `schema_app()`
  for the snapshot (every registered module, placeholder settings, no network),
  `python -m services.authoring_api [--host] [--port]` (default `127.0.0.1:58000`;
  exit 2 with `API not started: …` on bad settings).
- `services/openapi/authoring.json`: paths `/health`, `/auth/login`,
  `/auth/callback`, `/auth/session`, `/auth/logout`.
- `learning/policies.py`: `AuthorizationError(ValueError)`, raised by
  `authorize` with the same message. No other core change.
- `compose.identity.yml`: `quay.io/keycloak/keycloak:26.8.1@sha256:3f3c5f8e…7332`,
  `start-dev --import-realm --hostname=http://127.0.0.1:58080`, bound to
  `127.0.0.1:58080`; admin password, dev user password and client secret
  required from the environment.
- `infra/keycloak/alm-dev-realm.json`: realm `alm-dev`; confidential client
  `alm-authoring-api` (standard flow only, `pkce.code.challenge.method` S256,
  redirect `http://127.0.0.1:58000/auth/callback`); users `dev-admin`,
  `dev-learner`, `dev-unmapped` with fixed ids; secrets as `${…}` placeholders.
- `infra/keycloak/identity-map.dev.json`: `dev-admin` → `admin`, `dev-learner` →
  `learner` (the subjects of `tests/fixtures/alm/trusted-policy.json`).
- `docs/architecture/role-applications.md`: processes, job contract, module
  rules, errors and request ids, identity flow (D8–D10), configuration, manual
  smoke test.
- `tests/services/` (written first): `oidc_fixtures.py` (in-memory provider:
  local RSA key, JWKS, discovery and token endpoint through `httpx.MockTransport`),
  `test_api_common.py`, `test_api_identity.py`, `test_api_openapi.py`,
  `test_dev_identity.py`. Every API test blocks sockets and DNS with
  `tests.store_backends.block_network`.
- `.github/workflows/aimpro-contracts.yml`: job `api-skeleton` runs
  `python -m services.api_common.openapi --check` and the four test modules.

## Verification

Before the implementation: `unittest tests.services.test_api_common
tests.services.test_api_identity tests.services.test_api_openapi` → 3 errors,
`ModuleNotFoundError: No module named 'services'`.

During the implementation the identity tests found a deadlock (the JWKS lookup
held the client lock while calling discovery, which takes the same lock); fixed
before the commit.

On `d9262d8` (local, Python 3.12.7, telemetry disabled):

| Check | Result |
| --- | --- |
| `tests.services.*` (4 modules) | 46 tests, OK |
| `python -m services.api_common.openapi --check` | OK (exit 0) |
| `unittest discover -q`, `ALM_TEST_POSTGRES_URL` unset | 747 tests, OK, 107 skipped (701 + 46; skips unchanged) |
| `python -m aimpro.generate --check` | OK |
| `git diff --check` on the step files | OK |
| `docker compose -f compose.identity.yml config -q` without the variables | refused: `required variable … is missing a value` |

Acceptance tests by name:

- Login callback: `test_login_redirects_to_the_provider_with_pkce_state_and_nonce`,
  `test_callback_exchanges_the_code_with_the_verifier_and_sets_a_session_cookie`
  (verifier S256 equals the challenge; cookie `HttpOnly`, `Secure`, `SameSite=Lax`,
  path `/`), `test_state_must_match_the_browser_and_is_used_once`,
  `test_pending_login_expires`, `test_provider_error_and_refused_code_are_login_failures`,
  `test_return_path_is_kept_only_when_it_is_local`.
- Session: `test_session_reports_the_mapped_subject_and_never_the_tokens`,
  `test_requests_without_a_session_are_unauthenticated`, `test_session_expires_after_its_lifetime`.
- CSRF refusal: `test_writes_without_the_csrf_header_are_refused` (missing, empty,
  wrong), `test_csrf_token_of_another_session_is_refused`.
- Unmapped user 403: `test_unmapped_identity_is_forbidden_and_gets_no_session`,
  `test_same_subject_from_another_issuer_is_not_mapped`.
- Expired or foreign-issuer token: `test_invalid_id_tokens_are_refused` (expired,
  foreign issuer, other audience, extra audience without `azp`, nonce mismatch or
  missing, missing `exp`, foreign key with known and unknown `kid`, HS256),
  `test_unsigned_id_token_is_refused`, `test_discovery_with_another_issuer_is_refused` (502).
- Error mapping: `ErrorMappingTest` (409, 403 through the real `authorize`, 422
  for `ValueError`, record and request validation without the input text, 500
  without detail and logged with the request id, 404 and 405 in the same shape).
- Snapshot: `test_check_fails_on_drift_missing_or_extra_snapshots` (changed,
  reformatted, missing, extra file → exit 1), `test_checked_in_snapshot_matches_the_app`.

CI on `d9262d8` (Python 3.11; `fastapi 0.141.1`, `starlette 1.10.0` installed from
`requirements.txt`): push run
[42585455166](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42585455166)
and pull_request run
[42585505760](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42585505760):
`generated-contracts`, `authoring-architecture`, `store-backends`, `api-skeleton`,
`offline-evaluation` all pass. `api-skeleton` in the pull_request run: 46 tests, OK.
The commit that adds this handoff triggers a new CI run; its result is reported
in the PR, not here.

## Manual Keycloak smoke test

Throwaway secrets generated with `openssl rand -hex` into a mode-600 file outside
the repository; none is printed below.

```sh
docker compose -f compose.identity.yml up -d --wait     # … Container py-prototype-alm-keycloak-1 Healthy
curl -s http://127.0.0.1:58080/realms/alm-dev/.well-known/openid-configuration
# issuer http://127.0.0.1:58080/realms/alm-dev; code_challenge_methods_supported ['plain', 'S256']
# Keycloak log: "Realm 'alm-dev' imported", "Keycloak 26.8.1 on JVM (powered by Quarkus 3.40.1) started"
ALM_OIDC_ISSUER=… ALM_OIDC_CLIENT_ID=alm-authoring-api ALM_OIDC_REDIRECT_URI=http://127.0.0.1:58000/auth/callback \
ALM_OIDC_POST_LOGOUT_REDIRECT_URI=http://127.0.0.1:58000/ ALM_IDENTITY_MAP=infra/keycloak/identity-map.dev.json \
ALM_API_COOKIE_SECURE=false python -m services.authoring_api   # Uvicorn running on http://127.0.0.1:58000
```

A browser-like script (httpx, not committed) then followed the steps of
`docs/architecture/role-applications.md`, submitting the Keycloak login form.
Output:

```text
== dev-admin ==
GET /auth/login -> 302 http://127.0.0.1:58080/realms/alm-dev/protocol/openid-connect/auth
  Keycloak login page -> 200
  POST credentials -> 302 http://127.0.0.1:58000/auth/callback
GET /auth/callback -> 303 /studio
  Set-Cookie alm_session HttpOnly; Max-Age=3600; Path=/; SameSite=lax
  Set-Cookie alm_login expires=Mon, 09 Nov 2026 08:18:16 GMT; HttpOnly; Max-Age=0; Path=/auth; SameSite=lax
GET /auth/session -> 200 {'subject_key': 'admin', 'expires_at': '2026-11-09T09:18:16.456219Z', 'csrf_token': '<43 chars>'}
  body has token values: False
POST /auth/logout without CSRF -> 403 forbidden CSRF token missing or invalid
POST /auth/logout with CSRF -> 200 http://127.0.0.1:58080/realms/alm-dev/protocol/openid-connect/logout ['client_id', 'id_token_hint', 'post_logout_redirect_uri']
GET /auth/session after logout -> 401
GET provider logout URL -> 302 http://127.0.0.1:58000/
== dev-unmapped ==
GET /auth/login -> 302 http://127.0.0.1:58080/realms/alm-dev/protocol/openid-connect/auth
  Keycloak login page -> 200
  POST credentials -> 302 http://127.0.0.1:58000/auth/callback
GET /auth/callback -> 403 None {'error': 'forbidden', 'detail': 'Identity is not mapped to a policy subject', 'request_id': 'a647e41a04924546b91919c494f4414c'}
GET /auth/session -> 401
== health ==
GET /health -> 200 {'status': 'ok'} smoke-1
```

The login with the environment password also shows that Keycloak replaced the
`${…}` placeholders of the realm file. The API log contained neither the client
secret, nor the user password, nor a JWT (`grep -c` → 0, 0, 0). The `Secure`
flag is absent above only because `ALM_API_COOKIE_SECURE=false` for local HTTP.
The browser steps themselves (a real browser) were not run in this chat: not verified.
Afterwards the API was stopped and `docker compose -f compose.identity.yml down`
removed the Keycloak container.

## Acceptance items of #78

| Item | Status |
| --- | --- |
| `--check` fails on drift and passes on the snapshot; runs in CI | Done: `test_check_fails_on_drift_missing_or_extra_snapshots`, `test_checked_in_snapshot_matches_the_app`; CI job `api-skeleton` green |
| Unit tests cover login callback, session, CSRF refusal, unmapped user 403, expired or foreign-issuer token refusal | Done: tests listed above, 46 OK locally and in CI, network blocked |
| Error mapping covered for each class | Done: `ErrorMappingTest` (409, 403, 422 ×3, 500, 404/405) |
| Manual Keycloak smoke test recorded in the handoff | Done: section above (scripted; real-browser run not verified) |
| No core behaviour change; full offline suite green | Done: the only core change is the `AuthorizationError` subclass with the same message; 747 tests OK |

## Findings (not changed in this PR)

1. **Role refusals are 422, not 403.** Checks after `authorize` raise a plain
   `ValueError`: `Project authoring requires content authority`
   (`learning/projects.py`), `Subject is not an authorized participant`
   (`learning/context.py`), `Corpus source scope is not authorized`
   (`learning/service.py`). S05/S06 should decide whether they become
   `AuthorizationError` (with tests first).
2. **OpenAPI 422 schema.** FastAPI documents 422 with its default
   `HTTPValidationError`; the actual body is `{"error", "detail", "request_id"}`.
   S04 generates the client from this snapshot, so the error schema should be
   described there (for example by overriding the default responses).
3. **Sessions are process-local** (`MemorySessionStore`): a restart signs everyone
   out, one API process per user, no token refresh (the session ends after
   `ALM_API_SESSION_TTL`). A shared store is needed before a multi-process or
   shared deployment (D17).
4. **Access log carries the callback query.** Uvicorn's access log records
   `code`, `state`, `session_state` and `iss` of `/auth/callback`. The code is
   single-use and already redeemed, but a shared deployment should filter or
   disable this log.
5. **Server logs of a 500.** The response has no detail, but Starlette re-raises
   the exception after the handler, so uvicorn also logs the traceback with the
   exception message. Server-side only.
6. **RFC 9207 `iss` parameter.** Keycloak sends `iss` on the callback; the API
   ignores it and checks the issuer inside the ID token. Checking it too would
   add mix-up protection when several providers are configured.
7. **FastAPI is held at 0.141.1** by crewai's `opentelemetry-api~=1.42.0`.
   Starlette and `sse-starlette` are not pinned directly (CI installed
   `starlette 1.10.0`, `sse-starlette 3.7.0`; local has 3.6.0).
8. **FastAPI 0.141 includes routers lazily** (`_IncludedRouter`), so the CSRF
   guard inspects module routers before inclusion and refuses nested routers in
   a module. A later FastAPI may allow a simpler check.
9. **Fixed ports.** The issuer contains port 58080 and the client accepts only the
   redirect on port 58000; the realm file and the identity map change together.
10. **Smoke client and Keycloak cookies.** Keycloak sets its login cookies
    `Secure; SameSite=None`; httpx's cookie jar does not send them over HTTP
    (`LOGIN_ERROR … error="cookie_not_found"`), so the smoke script kept cookies
    itself. Browsers treat `127.0.0.1` as a secure context. S04's Playwright
    tests can replace the script.
11. **Test log noise.** Login refusals log warnings on `services.api_common`;
    without a handler they appear on stderr during tests.
12. **Roadmap baseline row.** As proposed in Chat 10 (finding 8): record S01–S03
    as done, the store row as "SQLite and PostgreSQL", and the web stack row as
    "`services/` with FastAPI 0.141.1; no `apps/` yet". This chat does not edit
    the roadmap.

## Open decisions

None blocked S03. S04 depends on D12 (front-end libraries), a proposed default
approved with the roadmap PR #73; S04 should confirm it was not changed.

## Next step

After the owner reviews and merges PR #79 (which closes #78): **S04 — Front-end
workspace and studio shell**, using the "Prompt for later steps" of the roadmap
with `chat-11.md` as the latest handoff.
