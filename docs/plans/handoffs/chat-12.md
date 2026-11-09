# Chat 12 handoff — S04 front-end workspace and studio shell

Date: 9 November 2026. Base: `main` at `dfd7652` (PR #79, S03, merged). Step:
**S04** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 0c).
Issue: [#80](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/80).

- Implementation commit: `138e116` on branch `feat/s04-frontend-studio-shell`,
  [PR #81](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/81).
- No model call, no live run, synthetic identities only. The only services used
  were a local Keycloak 26.8.1 from `compose.identity.yml`, the API on
  `127.0.0.1:58001` and the studio on `127.0.0.1:58000`. No backend code, realm
  file, identity map, store schema, ALM metamodel or AIM-PRO/jjodel export changed.

## Objective

A buildable front-end workspace with a studio that logs in and shows the
signed-in subject.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `gh pr view 79` | `MERGED` at `2026-11-09T08:40:51Z`, merge commit `dfd7652`; #78 closed |
| `git log --oneline -3` (after `git checkout main && git pull --ff-only`) | `dfd7652` (merge of #79), `4db1c37`, `d9262d8` |
| `gh pr list --state open` | none |
| `git status` | clean except the pre-existing untracked `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/` (not touched, not committed) |
| `unittest discover -q` with `LANGFUSE_ENABLED=false`, `CREWAI_DISABLE_TELEMETRY=true`, `CREWAI_TRACING_ENABLED=false` | 747 tests, OK, 107 skipped (as in the Chat 11 handoff) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | OK, OK |
| D12 | confirmed unchanged by the owner on 9 November 2026 |
| Toolchain | Node 22.22.2, npm 10.9.7, Docker 29.8.2 |

No difference from the Chat 11 handoff. Note: a first run with
`OTEL_SDK_DISABLED=true` added gave 2 failures and 5 errors, all in
`tests.test_telemetry` (that variable disables the SDK those tests use); with the
three variables above, as in earlier handoffs and CI, the suite is green.

## Versions

Exact versions, pinned in `apps/package.json` and `apps/package-lock.json`,
chosen among releases at least about two weeks old where possible:

| Package | Version | Note |
| --- | --- | --- |
| `react`, `react-dom` | 19.3.1 | |
| `react-router` | 8.5.0 | needs Node ≥ 22.22.0 |
| `i18next`, `react-i18next` | 26.5.11, 17.1.9 | 27.x and 18.x were days old |
| `openapi-typescript`, `openapi-fetch` | 7.13.0, 0.17.0 | `openapi-typescript` requires `typescript ^5.x` |
| `typescript` | 5.9.3 | |
| `vite`, `@vitejs/plugin-react` | 8.3.5, 6.1.2 | |
| `vitest`, `jsdom` | 5.1.0, 30.1.3 | see below |
| `@testing-library/react`, `@testing-library/dom` | 16.3.3, 10.4.2 | |
| `@types/react`, `@types/react-dom`, `@types/node` | 19.3.0, 19.3.0, 22.20.5 | |

`npm install` with npm 10.9.7 crashed (`Cannot read properties of null (reading
'edgesOut')` in arborist `#loadPeerSet`) with `vitest` 5.0.5 and 4.1.12, whose
exact optional peers (`@vitest/browser-playwright` and others) differ from the
latest published ones; `vitest` 5.1.0 (2 November 2026) installs, and so does
5.0.5 with npm 11.6.2. Hence `vitest` 5.1.0. Installs use `--ignore-scripts`
(no package needs an install script). Playwright (D12) is not a dependency yet;
it was used only outside the repository for the manual login below.

## Changes

`apps/` (npm workspace; commands run in `apps/`):

| Path | Content |
| --- | --- |
| `package.json`, `tsconfig*.json`, `vitest.config.ts` | workspaces `packages/api-client`, `packages/ui`, `packages/auth`, `studio`; scripts `build`, `typecheck`, `test`, `generate:client`, `check:client`; strict TypeScript (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `checkJs`); Vitest projects per workspace |
| `packages/api-client/scripts/generate.mjs` | `render`/`check`/`write` with `openapi-typescript` (alphabetized) from `services/openapi/authoring.json`; `--check` exits 1 with a message on drift, missing or hand-edited output; `--schema`/`--output` for tests |
| `packages/api-client/src/generated/authoring.ts` | generated client types (268 lines) |
| `packages/api-client/src/index.ts` | `createAuthoringClient` (`openapi-fetch`, `credentials: same-origin`, `cache: no-store`), `SessionView`, `LogoutView` types |
| `packages/ui/src/` | `tokens.css`, `styles.css` (visible `:focus-visible` outline 3 px, skip link, 44 px targets, reduced motion), `AppShell` (skip link, banner, `main` with `tabIndex=-1`), `Button` (`type=button`; busy: `aria-busy`, `aria-disabled`, clicks ignored, still focusable), `StatusMessage` (`status` or `alert`), `contrast.ts` |
| `packages/auth/src/` | `createSessionApi`: `readSession` (200 signed-in, 401 signed-out, 403 unmapped, other `SessionError`), `signOut` (header `X-CSRF-Token`; 401 → already signed out); `loginUrl` (local paths only, as the API); `SessionProvider`/`useSession` with states `loading`, `signed-in` (+ `signOutFailed`), `signed-out`, `unmapped`, `error` |
| `studio/` | `index.html` (title injected from the catalogue at build), `vite.config.ts` (base `/studio/`; dev and preview on `127.0.0.1:58000`; proxy `/auth`, `/health` to `ALM_STUDIO_API_URL`, default `http://127.0.0.1:58001`; `/` → 302 `/studio/`), `src/routes.tsx`, `src/shell/` (`StudioShell`, `NotFoundPage`), `src/features/{home,session}/`, `src/i18n/` (`en.json`, `i18next` instance, `CustomTypeOptions` so keys are type-checked) |
| `scripts/user-visible-strings.mjs`, `tests/user-visible-strings.test.ts` | TypeScript-AST scan of `packages/*/src` and `studio/src` `.tsx` files: JSX text with a letter, string literals as JSX children (also through `?:`, `&&`, `||`, `??`), literal `aria-label`, `aria-description`, `aria-placeholder`, `aria-roledescription`, `aria-valuetext`, `title`, `alt`, `placeholder`, `label` |
| `.gitignore` | `node_modules/`, `*.tsbuildinfo`; force-added because the root `.gitignore` ignores files named `.gitignore` |

Other files:

- `.github/workflows/aimpro-contracts.yml`: job `front-end` (Node 22.22.2, npm
  cache on `apps/package-lock.json`): `npm ci --ignore-scripts`,
  `npm run check:client`, `npm run typecheck`, `npm test`, `npm run build`.
- `docs/architecture/role-applications.md`: section "Front-end workspace"
  (packages, commands, the two-step API change, strings rule, serving in
  development, D17 for shared serving) and "With the studio" smoke test.

## Verification

Contract tests first: before any implementation, `npx vitest run` → 7 test files
failed, all on missing modules (`../scripts/generate.mjs`, `../src/index`,
`../src/contrast`, `@alm/api-client`, `../scripts/user-visible-strings.mjs`).

During the implementation: one studio test used `getByRole` before the session
had loaded (fixed in the test with `findByRole`); a CSS path in the token test
was rewritten by Vite's `new URL(…, import.meta.url)` transform (switched to
`node:path`).

On `138e116` (local, Node 22.22.2, Python 3.12.7):

| Check | Result |
| --- | --- |
| `npm ci --ignore-scripts` (after `rm -rf node_modules`) | added 136 packages |
| `npm run check:client` | exit 0 |
| `npm run typecheck` | OK (root scripts and the four workspaces) |
| `npm test` | 7 files, 62 tests, OK |
| `npm run build` | OK, no warning; `dist/index.html` has `<title>ALM Studio</title>` |
| `check:client` after editing `SessionView.subject_key` in the snapshot without regenerating | exit 1, `The generated API client differs from the OpenAPI snapshot; run npm run generate:client …`; snapshot restored, exit 0, `git status services/` clean |
| `t('home.missing')` in `HomePage.tsx` (temporary) | `tsc` error TS2345 listing the catalogue keys; file restored |
| `unittest discover -q`, telemetry off | 747 tests, OK, 107 skipped (unchanged) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | OK, OK |
| `git diff --check` | OK |

Token contrast (from the test inputs): text on background 16.56, muted text on
surface 7.12, link on background 7.21, white on accent 7.21, danger on danger
surface 5.75, focus on surface 5.65, strong border on background 4.61.

Acceptance tests by name:

- Build and tests in CI: job `front-end` (below).
- Client check: `generate.test.ts` — `matches the checked-in OpenAPI snapshot`,
  `fails when the snapshot changes without regeneration`, `passes again once the
  client is regenerated`, `fails when the generated client is missing or edited
  by hand`, `exits 1 from the command line on drift and 0 on the snapshot`; CI
  step `npm run check:client`.
- No hard-coded strings: `user-visible strings` — `are never hard-coded in the
  components of the workspace`, `scan every component file of the packages and
  apps`, `flag JSX text, string children and visible attributes`, `allow
  translated text, punctuation and non-visible attributes`; studio `English
  catalogue` tests.
- Session and shell: `session.test.tsx` (BFF calls, CSRF header, nothing in
  browser storage, sign-in/out navigation, failures) and `app.test.tsx`
  (sign-in, return path with query, signed-in banner, sign-out with CSRF,
  refused sign-out, unmapped, unavailable and retry, loading, not-found, skip link
  and document title).

CI on `138e116` (Ubuntu, Node 22.22.2, npm 10.9.7): push run
[42590926679](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42590926679)
and pull_request run
[42590957727](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42590957727):
`generated-contracts`, `authoring-architecture`, `store-backends`,
`api-skeleton`, `front-end`, `offline-evaluation` all pass. `front-end` in the
pull_request run: `npm ci` added 137 packages, `check:client` OK, 7 files and
62 tests passed, build OK. The commit that adds this handoff triggers a new CI
run; its result is reported in the PR, not here.

## Manual login through local Keycloak

Throwaway secrets generated with `openssl rand -hex` into a mode-600 file in the
session scratchpad (deleted afterwards); none is printed below.

```sh
docker compose -f compose.identity.yml up -d --wait   # Container py-prototype-alm-keycloak-1 Healthy
# discovery: issuer http://127.0.0.1:58080/realms/alm-dev, code_challenge_methods_supported ['plain', 'S256']
ALM_OIDC_ISSUER=http://127.0.0.1:58080/realms/alm-dev ALM_OIDC_CLIENT_ID=alm-authoring-api \
ALM_OIDC_REDIRECT_URI=http://127.0.0.1:58000/auth/callback ALM_OIDC_POST_LOGOUT_REDIRECT_URI=http://127.0.0.1:58000/ \
ALM_IDENTITY_MAP=infra/keycloak/identity-map.dev.json ALM_API_COOKIE_SECURE=false \
python -m services.authoring_api --port 58001          # Uvicorn running on http://127.0.0.1:58001
cd apps && npm run dev --workspace @alm/studio          # VITE v8.3.5 ready, http://127.0.0.1:58000/studio/
curl http://127.0.0.1:58000/health                      # {"status":"ok"} (through the proxy)
curl -w '%{http_code} %{redirect_url}' http://127.0.0.1:58000/   # 302 http://127.0.0.1:58000/studio/
```

Google Chrome (headless) was driven with `playwright-core` 1.64.1 installed in
the scratchpad (not committed), filling the real Keycloak login form. Output on
the dev server:

```text
== dev-admin ==
GET http://127.0.0.1:58000/studio/ -> title "ALM Studio", h1 "Sign in to the studio"
  first Tab focuses: "Skip to main content"
  Keycloak login page: /realms/alm-dev/protocol/openid-connect/auth
After login: http://127.0.0.1:58000/studio/
  banner: "ALM Studio |  | Signed in as admin | Sign out"
  h1: "Studio"
  cookie alm_session: httpOnly=true sameSite=Lax path=/ secure=false
  script-visible state: {"documentCookie":"","localStorage":0,"sessionStorage":0}
  GET /auth/session -> {"status":200,"subject_key":"admin","keys":["csrf_token","expires_at","subject_key"]}
  POST /auth/logout without CSRF -> 403
After sign-out: http://127.0.0.1:58000/studio/ h1 "Sign in to the studio"
  GET /auth/session -> 401
  sign in again asks for credentials: true
== dev-unmapped ==
  callback -> /auth/callback: {"error":"forbidden","detail":"Identity is not mapped to a policy subject"}
  studio afterwards: h1 "Sign in to the studio"
```

The same script against the production build (`npm run build`, then
`npm run preview --workspace @alm/studio` on 58000) gave the same lines; there
`/` → 302 `/studio/` and `/studio/projects` → 200 (SPA fallback). Screenshots
of the dev-server run (sign-in page with the skip link focused, signed-in shell)
were checked visually; those of the preview run were not looked at. Browser console: the expected 401 (session checks while signed out)
and 403 (CSRF probe, unmapped callback), plus one 404 for `/favicon.ico`. The
API and studio logs contained neither the client secret, nor the user password,
nor a JWT (`grep -c` → 0 each). Afterwards the studio, the API and Keycloak were
stopped (`docker compose -f compose.identity.yml down` removed the Keycloak
container; the `py-prototype_default` network stays, used by other existing
containers). A person at a visible browser did not run these steps: the run was
automated, headless Chrome.

## Acceptance items of #80

| Item | Status |
| --- | --- |
| `npm run build` and `npm test` pass in CI | Done: job `front-end` green in both runs on `138e116` (62 tests, build OK) |
| The client check fails when the snapshot changes without regeneration | Done: `generate.test.ts` (5 tests), manual run exit 1, CI step `check:client` |
| No user-visible string is hard-coded in components (lint rule or test) | Done: `tests/user-visible-strings.test.ts` with positive and negative fixtures; the page title also comes from the catalogue |
| Manual login through local Keycloak reaches the shell (recorded in handoff) | Done: section above, dev server and production build (automated headless Chrome) |

## Findings (not changed in this PR)

1. **Chat 11 finding 2 still open.** The generated client types 422 as FastAPI's
   `HTTPValidationError`, and 401/403/409/500 bodies are not documented at all.
   S04 does not need them (`/auth/session` and `/auth/logout` have no 422; the
   auth package uses status codes). S05 adds the first business endpoints and
   should describe `ErrorBody` for every error status in the snapshot, then
   regenerate the client.
2. **Unmapped login shows raw JSON.** `/auth/callback` answers 403 with the JSON
   error body, so a user who is not mapped sees JSON instead of a studio page.
   A redirect to a studio error page would need a backend change (S03 scope).
3. **Serving outside development.** Vite forwards `/auth` and `/health` only;
   S05 must add its API prefix to `proxy` in `studio/vite.config.ts`. How a
   shared deployment serves the build (API static mount or reverse proxy) is D17.
4. **npm 10 peer bug.** `vitest` 5.0.5 and 4.1.12 crash `npm install` on npm
   10.9.7 (see Versions). Upgrading `vitest` must keep its optional peer versions
   equal to the latest published ones, or use npm 11.
5. **Root `.gitignore` ignores `.gitignore` files** (and `lib/`, `dist/`, `build/`
   anywhere). `apps/.gitignore` was force-added; a front-end folder named `lib`
   would be ignored silently.
6. **No favicon.** `/favicon.ico` is 404 on the studio.
7. **Session expiry is not shown or handled in the UI.** When the session ends
   (`ALM_API_SESSION_TTL`), the next call returns 401; the shell only re-reads the
   session on load or retry. S07 should handle 401 on any call by returning to
   sign-in.
8. **No accessibility engine yet.** Contrast, landmarks, skip link, focus and
   roles are tested; an axe check is planned in S07 (roadmap acceptance).
9. **Strings rule is a heuristic.** It sees literals in JSX and in `?:`, `&&`,
   `||`, `??` branches, not strings built in variables and passed as props.
10. **Roadmap baseline row** (Chat 11 finding 12, extended): record S01–S04 as
    done and the web stack row as "`services/` with FastAPI 0.141.1; `apps/` npm
    workspace with React 19, Vite 8, studio shell". This chat does not edit the
    roadmap.

## Open decisions

None blocked S04. S05 depends on D10 (policy resolution) and D15 (synthetic
seed), proposed defaults approved with the roadmap PR #73; S05 should confirm
they were not changed.

## Next step

After the owner reviews and merges PR #81 (which closes #80): **S05 — Read-only
Authoring API**, using the "Prompt for later steps" of the roadmap with
`chat-12.md` as the latest handoff.
