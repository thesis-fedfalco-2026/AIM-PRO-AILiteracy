# Prototype roadmap — role applications over ALM

Prepared on 8 November 2026 at `main` `64b6a7e` (PR #72 merged). This is the
execution plan for the working prototype. It is not evidence that any step is
done. Architecture and module rules come from the
[role-applications plan](role-applications-plan.md); this file fixes the order,
the scope of each step and how each chat works. If the two disagree, this file
wins until the owner changes it.

## Direction

- **ALM is the reference model.** The prototype is built on the ALM service and
  its contracts. The AIM-PRO metamodel will be revised and SCN01 will be replaced
  by other scenarios. AIM-PRO mappings are later work and block no step. AIM-PRO
  and jjodel exports are never edited.
- **Goal:** a working prototype for each human role (reviewer, author, learner,
  then organisation), reached through small, verified steps.
- **One state authority.** `LearningService` and its store own every write.
  Applications never call agents, models, the database or MCP directly.
- **Every generated artefact is a proposal** that a human decides and applies.

## Verified baseline (8 November 2026)

| Fact | Value | How verified |
| --- | --- | --- |
| `main` | `64b6a7e` | `git log --oneline -1` |
| Offline suite | 570 tests OK, 4 skipped | `unittest discover -q` with telemetry off |
| Generated contracts | OK | `python -m aimpro.generate --check` |
| CI jobs | `generated-contracts`, `authoring-architecture`, `offline-evaluation` | `.github/workflows/aimpro-contracts.yml`; CI uses Python 3.11, local `.venv` is 3.12.7 |
| Store | SQLite only, in `learning/store.py` | direct `store.db` use in 10 core modules: `learning/{service,generation,projects,releases,decisions}.py`, `aimpro/{source_service,syllabus_service,bindings,execution_setup,trace}.py`; 12 test modules also use it |
| Release/import | `learning/releases.py` (R1) | PR #72; guide `docs/architecture/releases.md` |
| Activation | refused while an ASSESS activity has no runtime role (D4) | `RELEASE_RUNTIME_ROLE` in `learning/releases.py` |
| Web stack | none yet: no `services/`, no `apps/`, no FastAPI dependency | `ls`, `requirements.txt` |
| Toolchain | Node 22.22.2, Docker 29.8.2; `psycopg[binary]==3.2.12` already pinned | local commands |
| Repository | `thesis-fedfalco-2026/AIM-PRO-AILiteracy` (renamed from `py-prototype`) | `gh repo view` |

Facts in this table are a snapshot. Every chat re-verifies the ones it uses.

## Owner decisions in force

| Id | Decision | Date |
| --- | --- | --- |
| Stack | FastAPI backend; React + TypeScript + Vite front-end, one app per audience | 8 Nov 2026 |
| Identity | Keycloak OIDC from the start | 8 Nov 2026 |
| Store | ALM store on PostgreSQL now (SQLite kept for tests and single-host use) | 8 Nov 2026 |
| UI language | English first, externalised strings | 8 Nov 2026 |
| D1–D5 | R1 scope, manifest format 1, policy preview, D4 = a, tracking in #71 | 8 Nov 2026 |
| Earlier | Socratic option b; live model runs only with owner authorization; never edit AIM-PRO/jjodel exports | see `docs/architecture/agentic-network-decisions.md` |

## Proposed defaults to confirm when this roadmap is reviewed

These close choices that would otherwise be made differently by different
chats. Approving the roadmap PR approves them; any row can be changed in review.

| Id | Topic | Proposed default | Needed by |
| --- | --- | --- | --- |
| D8 | Browser authentication pattern | Backend-for-frontend: the API runs the OIDC code flow with PKCE, keeps tokens server-side, sets an `HttpOnly` `SameSite=Lax` session cookie, and requires a CSRF header on writes. No token in the browser. | S03 |
| D9 | Identity → subject key | A host-side `identity-map.json` maps (issuer, `sub`) to a policy `subject_key`. Keycloak roles grant nothing; the trusted policy stays the only authority. Unmapped users get 403. | S03 |
| D10 | Policy resolution in a multi-context API | A configured directory of trusted policy files; for each request the API loads the file whose `policy_ref` equals the context's `policies` ref. No match → the context is unavailable (activation requires the installed preview, as today). | S05 |
| D11 | Python libraries | `fastapi`, `uvicorn`, `pyjwt[crypto]` (JWKS validation), `httpx` (already pinned) for the OIDC client; exact versions pinned in `requirements.txt` | S03 |
| D12 | Front-end libraries | npm workspaces; `openapi-typescript` + `openapi-fetch` for the client; `react-router`; `i18next` with JSON catalogues; Vitest for units; Playwright for browser tests | S04 |
| D13 | PostgreSQL write serialization | One transaction-scoped advisory lock (`pg_advisory_xact_lock`) per write transaction, matching SQLite `BEGIN IMMEDIATE`; reads in `REPEATABLE READ`; payloads stored as canonical JSON `TEXT` (not `jsonb`) so bytes stay identical; an insertion sequence column replaces `rowid` ordering | S02 |
| D14 | Jobs store | Separate tables in a separate PostgreSQL schema (`jobs`), never in the ALM tables; the ALM `request_id` stays the idempotency key | S08 |
| D15 | Synthetic demo data | A dev-only seed command builds a database through the production commands with synthetic model responses (the existing test fixtures), used by API tests, UI development and browser tests | S05 |

Open decisions that block later steps, not decided here:

| Id | Decision | Blocks |
| --- | --- | --- |
| G7 / D4 lift | Runtime assessor role and evaluation adapter, and the explicit decision that lets activation proceed when it exists | S11 and every learner step |
| D16 | Scenario input independent of the AIM-PRO export (today the Curator reads the AIM-PRO project export) | nothing before S13; needed when scenarios change |
| D17 | Deployment owner and shared environment | any shared deployment |
| D6 | Sending the convergence draft to `rik99` | nothing in this roadmap |
| Decision 6 details | Organisation documents and guidance | S15 |
| Decision 3, #28, #17, #19 | Learner data, governance, twins, dashboards | Phase 7 of the role plan; not scheduled here |

## Working protocol for every chat

Each step is one chat and normally one PR. A step may need a second chat; it
then continues the same step id.

1. **Start by verifying.** Read `AGENTS.md`, this file, the previous handoff and
   the files the step names. Run: `git status`, `git log --oneline -3`,
   `gh pr list --state open`, the step's baseline test command. Report any
   difference from what the previous handoff says before changing anything.
2. **Open the step issue.** Create a GitHub issue titled with the step id, with
   the step's acceptance list as a checklist. Work against that issue.
3. **Stay in scope.** Do only what the step lists. Anything else found goes into
   the handoff under "Findings", not into the PR.
4. **Never decide for the owner.** If an open decision blocks the step, stop and
   ask. Do not pick an option and continue.
5. **Contracts before code.** Write or extend the contract test first (schema,
   OpenAPI snapshot, store interface, parity test), then the implementation.
6. **Evidence for every claim.** The handoff quotes commands and their results,
   commits and CI run links. Anything not verified is written as "not verified".
   Never infer an earlier state from memory or from a previous chat.
7. **Verification before publishing.** Run the step's commands plus the full
   offline suite and `python -m aimpro.generate --check`. Publish a focused PR,
   wait for CI and report its result.
8. **Handoff.** Write `docs/plans/handoffs/chat-NN.md` (next free number) with:
   step id, objective, changes, PR and commits, verification, findings, open
   decisions and the exact next step id. Include it in the PR.
9. **Plan changes.** A chat never edits this roadmap on its own initiative. It
   proposes a change in the handoff; the owner applies it in a PR.

Stop and report instead of continuing when: a test that passed at the start now
fails for reasons outside the step; the step needs a model call, a live run or
real data; an AIM-PRO/jjodel export would change; or the step's acceptance
cannot be met within its scope.

Standing limits for all steps: no model calls without explicit owner
authorization; tests use synthetic data and block outbound network except the
explicitly configured local test services (PostgreSQL, Keycloak) of the step;
no learner personal data; no change to AIM-PRO/jjodel exports or to the ALM
metamodel.

## Steps

| Step | Role-plan phase | Result | Depends on |
| --- | --- | --- | --- |
| S01 | 0a | Store transaction API; no SQL outside `learning/store.py` | this roadmap |
| S02 | 0b | PostgreSQL store backend, copy tool, CI service | S01 |
| S03 | 0c | API skeleton, OpenAPI check, OIDC with Keycloak | S02, D8, D9, D11 |
| S04 | 0c | Front-end workspace and studio shell with login | S03, D12 |
| S05 | 1 | Read-only Authoring API, policy resolver, synthetic seed | S04, D10, D15 |
| S06 | 2 | Review endpoints: decide and apply with review key | S05 |
| S07 | 2 | Studio review inbox — **milestone M1: first usable app** | S06 |
| S08 | 3 | Agent job worker and progress stream | S07, D14 |
| S09 | 4 | Studio authoring: projects, generation, sources | S08 |
| S10 | 8 | Studio release and delivery views — **milestone M2: authoring to delivery** | S09 |
| S11 | — | Runtime assessor role and evaluation adapter (G7) | S10, owner decision |
| S12 | 5 | Learner API | S11 |
| S13 | 5 | Learner app — **milestone M3: learner practice end to end** | S12 |
| S14 | — | Scenario input independent of the AIM-PRO export | D16 |
| S15 | 6 | Organisation context and guidance | decision 6 details |

S14 and S15 are listed so they are not forgotten; they are specified when their
decisions exist. Phase 7 of the role plan (competence discovery, monitoring)
stays blocked.

### S01 — Store transaction API

**Goal.** Every core use of the database goes through `LearningStore` methods,
so a second backend can be added without touching business code.

**Scope.**

- Add to `LearningStore`: a write-transaction context manager (today
  `with store.db: store.db.execute('BEGIN IMMEDIATE')`), a read-transaction
  context manager (today `BEGIN`), an `in_transaction` property, request
  reservation (today `INSERT INTO requests …` in `projects.py`, `releases.py`),
  and a query for recorded request results (today `releases._recorded`).
- Replace the direct `store.db` uses in the 10 core modules listed in the
  baseline. Keep their transaction boundaries exactly.
- Add an architecture test that fails when `learning/` or `aimpro/` (except
  `learning/store.py`) contains `.db.`, `execute(` on a store connection, or SQL
  keywords in string literals.

**Not in scope.** PostgreSQL; schema changes; changing tests that inspect SQLite
directly, unless they break (they may keep `store.db`).

**Acceptance.**

- [ ] No direct database access outside `learning/store.py` in `learning/` and `aimpro/`, enforced by a test.
- [ ] Transaction boundaries unchanged: the existing concurrency and replay tests (`test_authoring_projects`, `test_releases`, `test_learning_store`) pass unchanged.
- [ ] Full offline suite and `aimpro.generate --check` pass; CI green.

### S02 — PostgreSQL store backend

**Goal.** The ALM store runs on PostgreSQL with the same guarantees as SQLite.

**Scope.**

- A backend selected by URL: a file path or `sqlite:///…` keeps SQLite;
  `postgresql://…` uses psycopg 3. Same logical tables (entities, contexts,
  operations, requests) and schema version, following D13.
- Same guarantees: serialized writes, consistent read snapshots, immutable
  versions, exact request replay, latest-by-insertion in `owned`.
- A test helper that runs a chosen set of suites on both backends:
  `test_learning_store`, `test_learning_service`, `test_learning_decisions`,
  `test_authoring_projects`, `test_releases`, `test_authoring_cycle`. PostgreSQL
  runs only when `ALM_TEST_POSTGRES_URL` is set; the network blocker allows only
  that host.
- `python -m learning.copy_store --from <sqlite path> --to <postgresql url>`:
  one-way copy, refuses a non-empty target, verifies row counts and payload
  hashes.
- CI: a job with a `postgres:17` service container running those suites.
- `compose.alm.yml` with a local PostgreSQL for development.

**Not in scope.** Moving existing local databases; the jobs schema (S08).

**Acceptance.**

- [ ] The listed suites pass on both backends, locally and in CI.
- [ ] Concurrent identical requests on PostgreSQL produce one recorded result (port of the existing SQLite concurrency test).
- [ ] Canonical payload bytes are identical after a round trip on both backends.
- [ ] The copy tool reproduces a synthetic database; counts and hashes match.
- [ ] SQLite behaviour is unchanged; full offline suite green.

### S03 — API skeleton and identity

**Goal.** A FastAPI service skeleton that authenticates users through Keycloak
and maps them to policy subjects, with no business endpoint yet.

**Scope.**

- `docs/architecture/role-applications.md`: process boundaries, job contract,
  module rules, identity flow (from the role plan, updated with D8–D10).
- `services/api_common/`: app factory, module registry, error mapping
  (`StateConflict` → 409, authorization failure → 403, validation → 422,
  anything else → 500 without detail), request-id propagation, health endpoint.
- Authorization errors need a distinct type: add `AuthorizationError(ValueError)`
  in `learning/policies.py`, raised by `authorize`; existing callers keep working.
- OIDC per D8/D9: login, callback, logout, session store, CSRF check,
  `identity-map.json` loader. Unit tests use a locally generated key pair and an
  in-memory JWKS, with no network.
- `compose.identity.yml` with a pinned Keycloak image and a checked-in dev realm
  export (synthetic users only); a documented manual smoke test.
- OpenAPI snapshot in `services/openapi/authoring.json` and
  `python -m services.api_common.openapi --check`, run in CI.

**Acceptance.**

- [ ] `--check` fails on drift and passes on the snapshot; runs in CI.
- [ ] Unit tests cover login callback, session, CSRF refusal, unmapped user 403, expired or foreign-issuer token refusal.
- [ ] Error mapping covered for each class above.
- [ ] Manual Keycloak smoke test recorded in the handoff (commands and result).
- [ ] No core behaviour change; full offline suite green.

### S04 — Front-end workspace and studio shell

**Goal.** A buildable front-end workspace with a studio that logs in and shows
the signed-in subject.

**Scope.** `apps/` with npm workspaces (D12): `packages/api-client` generated from
the OpenAPI snapshot, `packages/ui` (tokens and base components meeting WCAG 2.1
AA), `packages/auth` (session calls to the BFF), `studio/` shell with login,
logout and an English string catalogue. CI job: install, type-check, unit tests,
build, and a check that the generated client matches the snapshot.

**Acceptance.**

- [ ] `npm run build` and `npm test` pass in CI.
- [ ] The client check fails when the snapshot changes without regeneration.
- [ ] No user-visible string is hard-coded in components (lint rule or test).
- [ ] Manual login through local Keycloak reaches the shell (recorded in handoff).

### S05 — Read-only Authoring API

**Goal.** Staff can read contexts, proposals and projects through the API.

**Scope.**

- Policy resolver (D10).
- Synthetic seed command (D15), building contexts, a project, pending and applied
  proposals and a release through the production commands.
- Endpoints: context summary (`show`), pending proposals with exact payload and
  review payload key, project inspection, approved project syllabus, release
  inspection (`show-release`). Response models built from existing records; no
  raw store rows.
- Parity tests: for each endpoint, the same references as the CLI on the same
  seeded database.

**Acceptance.**

- [ ] Each endpoint has a parity test with the CLI.
- [ ] A learner-only subject gets the same redaction as `show` today.
- [ ] A context whose policy file is not installed is reported as unavailable.
- [ ] Endpoints never write (database change counter unchanged).
- [ ] OpenAPI snapshot updated; client regenerated.

### S06 — Review endpoints

**Goal.** Decide and apply through the API with the same guarantees as the CLI.

**Scope.** `decide` requires the reviewed payload key the client saw; a mismatch
returns 409. `apply` requires an operation id; replay returns the same change.
Add a service method that takes the expected key, if needed, with tests first.

**Acceptance.**

- [ ] A stale key is refused with 409 and records nothing.
- [ ] CLI and API decisions are interchangeable on the same database (tests both ways).
- [ ] Reviewer-role checks are unchanged (administrative, content, assessment authority).
- [ ] CSRF required on both endpoints.

### S07 — Studio review inbox (M1)

**Goal.** A reviewer completes a review in the browser.

**Scope.** Pending queue; payload viewer with diagnostics; diff against the
previously applied version of the same artefact; separate approve and apply
steps; conflict handling (reload on 409). Playwright tests on the seeded
database.

**Acceptance.**

- [ ] Browser test: review and apply an Evaluator proposal on the seed database.
- [ ] Browser test: a payload changed after loading is refused and reloaded.
- [ ] Accessibility check (axe) passes on the inbox views.
- [ ] Handoff includes a short owner test script for teacher validation.

### S08 — Agent job worker

**Goal.** Generation runs in a worker, outside HTTP requests, with progress.

**Scope.** `services/jobs`: job store (D14), job-kind registry with one entry per
existing generator and Curator command, worker loop, in-memory event sink fed by
`agent_system/events.py`, server-sent-events endpoint, abandon mapping. Model
credentials load only in the worker. Tests use the synthetic generator models.

**Acceptance.**

- [ ] A queued Evaluator job ends as a pending proposal visible in the inbox.
- [ ] A replayed `request_id` returns the same job and constructs no model.
- [ ] An interrupted job can be abandoned by an administrator.
- [ ] The event stream carries no content (strict event log in tests).
- [ ] The API process imports no model client (test).

### S09 — Studio authoring

**Goal.** An author runs the authoring cycle from the studio.

**Scope.** Project initialization and revision; job forms for Curator,
Evaluator, Teacher and Trainer showing the exact inputs; source preparation with
licence verdicts as usage conditions; binding proposals. The Design Agent
conversation stays out.

**Acceptance.**

- [ ] Browser test: the synthetic authoring cycle reaches the same project state as `tests/test_authoring_cycle.py`.
- [ ] Each form shows the exact refs it sends; a stale base is refused and reloaded.

### S10 — Release and delivery views (M2)

**Goal.** Release, import and activation from the studio.

**Scope.** Views over `propose-release`, `show-release`, `propose-delivery-import`
(binding selection, policy preview download) and `propose-activation` (findings
shown, including the D4 refusal). Installing a policy preview stays a host
operator action, documented, not a browser action.

**Acceptance.**

- [ ] Browser test: release and import of the seeded project; activation shows `RELEASE_RUNTIME_ROLE`.
- [ ] The policy preview is shown in full and never replaces an installed policy.

### S11 — Runtime assessor role (G7)

**Goal.** ASSESS activities get a reviewed runtime role, so that activation can
be considered.

**Scope.** Specified in its own chat from G7 in
`docs/plans/handoffs/chat-07.md` and the evaluation flow in
`docs/architecture/authoring-lifecycle.md`. It needs an explicit owner decision
on how D4 is lifted before implementation.

**Acceptance.** Defined with the owner when the step starts.

### S12 — Learner API

**Goal.** A separate learner process with LEARNING redaction.

**Scope.** Learner request as a job, attempt submission, own progress
(occurrences and approved states only). No authoring code importable.

**Acceptance.**

- [ ] A learner reaches only their own data (tests across two learners).
- [ ] Evaluations stay proposed and approved separately.
- [ ] `python -m evaluation --check` still passes.

### S13 — Learner app (M3)

**Goal.** A learner practises in the browser on an activated synthetic delivery.

**Scope.** Practice screen with the Socratic coach, progress view. Choosing
between alternative next exercises waits for decision 1.

**Acceptance.**

- [ ] Browser test: practice, submission and a reviewed evaluation on the seed delivery.
- [ ] The learner build contains no authoring code (bundle check).

## Chat prompts

Copy the prompt for the next step. Replace `NN` with the next free handoff number.

### Prompt for S01

```text
Work in /Users/juridirocco/development/py-prototype (GitHub:
thesis-fedfalco-2026/AIM-PRO-AILiteracy). Read AGENTS.md,
docs/plans/prototype-roadmap.md (sections "Working protocol" and "S01"), the
latest docs/plans/handoffs/chat-NN.md, learning/store.py and every core module
the S01 scope lists. Chat in Italian; write code, docs and GitHub content in
English. Do not spawn agents. Follow the working protocol exactly: verify the
baseline first, open the S01 issue, stay in scope, stop on any open decision.

Implement S01. Write the architecture test first, then move each direct database
use behind LearningStore methods without changing transaction boundaries.
No PostgreSQL work, no schema change, no model calls.

Run the S01 acceptance commands, the full offline suite and
python -m aimpro.generate --check. Publish a focused PR, check CI, and write the
handoff with evidence and the next step id.
```

### Prompt for later steps

```text
Work in /Users/juridirocco/development/py-prototype (GitHub:
thesis-fedfalco-2026/AIM-PRO-AILiteracy). Read AGENTS.md,
docs/plans/prototype-roadmap.md (sections "Working protocol", the step SNN and
any decision it depends on), the latest docs/plans/handoffs/chat-NN.md and the
files the step names. Chat in Italian; write code, docs and GitHub content in
English. Do not spawn agents. Follow the working protocol exactly: verify the
baseline first, confirm the step's dependencies are merged and its decisions are
recorded, open the step issue, stay in scope, stop on any open decision.

Implement step SNN as written. Contract tests first. No model calls or live runs
without explicit owner authorization; synthetic data only.

Run the step's acceptance checks, the full offline suite and
python -m aimpro.generate --check. Publish a focused PR, check CI, and write the
handoff with evidence and the next step id.
```
