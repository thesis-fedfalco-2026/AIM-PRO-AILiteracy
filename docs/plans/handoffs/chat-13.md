# Chat 13 handoff — S05 read-only Authoring API

Date: 9 November 2026. Base: `main` at `837cc10` (PR #81, S04, merged). Step:
**S05** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 1).
Issue: [#82](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/82).

- Implementation commit: `69c4689` on branch `feat/s05-read-only-authoring-api`,
  [PR #83](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/83).
- No model call, no live run, synthetic data only. Services used: a throwaway
  local PostgreSQL 17 container (removed afterwards) and the API process on
  `127.0.0.1:58011` for a smoke test. Keycloak was not started. No ALM
  metamodel, store schema, realm file, identity map or AIM-PRO/jjodel export
  changed.

## Objective

Staff can read contexts, proposals and projects through the API.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `gh pr view 81` | `MERGED`, merge commit `837cc10` |
| `git log --oneline -3` (after `git checkout main && git pull --ff-only`) | `837cc10` (merge of #81), `fef949a`, `138e116` |
| `gh pr list --state open` | none |
| `git status` | clean except the pre-existing untracked `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/` (not touched, not committed) |
| `unittest discover -q`, telemetry off (`LANGFUSE_ENABLED=false`, `CREWAI_DISABLE_TELEMETRY=true`, `CREWAI_TRACING_ENABLED=false`) | 747 tests, OK, 107 skipped |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | OK, OK |
| D10, D15 | confirmed unchanged by the owner on 9 November 2026 |

No difference from the Chat 12 handoff.

**Scope addition by the owner (9 November 2026):** Chat 12 finding 1. The
OpenAPI snapshot now documents the real error body for every error status, and
the client is regenerated. It is listed in the scope of #82.

## Changes

Backend (`services/`):

| Path | Content |
| --- | --- |
| `api_common/contexts.py` | `PolicyDirectory` (D10): the `*.json` file whose `policy_ref` equals the context's `policies` reference, re-read on every request; an invalid file or a reference installed twice raises `PolicyDirectoryError` (500, not a `ValueError`). `ContextServices.open(context_id)`: opens the store, resolves the policy, yields a `LearningService` whose orchestrator factory refuses, and closes the store. A missing context and a missing policy raise `ContextUnavailable('no such context' / 'policy not installed')`. `context_reader` adds `Cache-Control: no-store`. `READ_ERRORS` |
| `api_common/errors.py` | `ContextUnavailable` → 404 `context_unavailable`, fixed detail `Context unavailable`, the reason is logged with the request id; `ValidationIssue` (`loc`, `msg`, `type`) types `ErrorBody.detail`; `error_responses(*statuses)` for the OpenAPI `responses` |
| `api_common/settings.py` | `store` (`ALM_STORE`, `SecretStr`), `policy_dir` (`ALM_POLICY_DIR`) |
| `api_common/app.py`, `api_common/auth.py` | documented error statuses on `/health` (500), `/auth/login` (422, 500, 502), `/auth/callback` (401, 403, 422, 500, 502), `/auth/session` and `/auth/logout` (401, 403, 500) |
| `authoring_api/context_summary.py`, `review.py`, `projects.py`, `releases.py` | modules `contexts`, `review`, `projects`, `releases` (routes below) |
| `authoring_api/app.py` | registry with the four modules; when any module is selected, `ALM_STORE` and `ALM_POLICY_DIR` are required and checked at start (a missing SQLite file is refused and never created); `VERSION` 0.2.0 |
| `openapi/authoring.json` | regenerated: 10 paths, no `HTTPValidationError`/`ValidationError` schemas |

| Module | Route | Response | CLI equivalent |
| --- | --- | --- | --- |
| `contexts` | `GET /contexts/{context_id}` | `ContextSummary` | `show` |
| `review` | `GET /contexts/{context_id}/pending-proposals` | `PendingProposals` (`proposal`, `candidates`, `review_payload_key`) | `show` + the `decide` preview |
| `projects` | `GET /contexts/{context_id}/projects/{project_id}` | `ProjectInspection` | `show-authoring-project` |
| `projects` | `GET /contexts/{context_id}/resources/{resource_id}/versions/{version}/project-syllabus` | `ApprovedSyllabus` | `show-project-syllabus` |
| `releases` | `GET /contexts/{context_id}/resources/{resource_id}/versions/{version}/release` | `ReleaseInspection` | `show-release` |

Core (`learning/`):

- `review.py`: `PendingProposal` record and `pending_proposals(store, context)`:
  the latest revision of every `AWAITING_DECISION` proposal of the context, newest
  first, with `proposal_candidates` and `review_payload_key(proposal, candidates)`.
- `service.py`: `LearningService.pending_proposals` (in a read transaction;
  empty for a learner-only subject) and `_learner_only`, now shared with `show`.
  The behaviour of `show` is unchanged.

Seed (D15): `tests/seed.py`, `python -m tests.seed --output DIR [--db LOCATION]`.
It writes `alm.sqlite` (unless `--db`), `policies/architecture-policy-1.json`
(installed), `policy-previews/architecture-policy-<version>.json` (not installed)
and `seed.json` (`SeedManifest`: contexts, subjects, project, release, delivery
policy reference, pending proposals). It never writes a PostgreSQL URL to disk.
State: `architecture-authoring` holds the applied syllabus, project, three
generations, completion rules and release, plus a pending Evaluator revision
(`generate('ASSESSMENT', '2')`). `architecture-delivery` holds the applied import,
whose policy preview is not installed. `architecture-delivery-2` holds a pending
import, with `learner` as a participant. It is built by `ProductionAuthoring` from
`tests/authoring_cycle_fixtures.py`, so only model and retrieval responses are
synthetic.

Front-end (`apps/`): client regenerated
(`packages/api-client/src/generated/authoring.ts`, 1377 lines), `ErrorBody`
type exported from `@alm/api-client`, `/contexts` added to the Vite proxy.

Other: `docs/architecture/role-applications.md` (errors table, D10 details,
configuration, sections "Read-only authoring endpoints (S05)" and "Synthetic
seed (D15)", smoke-test steps); CI test lists in
`.github/workflows/aimpro-contracts.yml` (`authoring-architecture`:
`test_seed`, `test_learning_review`; `store-backends`: those two plus
`test_authoring_read_api`; `api-skeleton`: `test_api_contexts`,
`test_authoring_read_api`).

## Verification

Contract tests first. Before any implementation the new and changed test
modules gave `Ran 11 tests`, `FAILED (failures=2, errors=5)`. The 5 errors were
import failures (`No module named 'tests.seed'` ×3,
`No module named 'services.api_common.contexts'` ×2). The 2 failures were the
OpenAPI tests: the endpoint list, and `HTTPValidationError` still present.

During the implementation:

- An import cycle `auth → errors → contexts → auth` was fixed by defining
  `ContextUnavailable` in `errors.py`.
- One test assumed older project revisions appear in `store.history(AUTH)`.
  `Resource` is domain configuration with no owner, so the test now takes the
  older revision from the applied proposals' candidates.

On `69c4689` (local, Python 3.12.7, Node 22.22.2):

| Check | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 798 tests, OK, 125 skipped (+51 tests, +18 skips: the PostgreSQL copies) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | OK, OK, OK |
| new modules and the CI `store-backends` list with `ALM_TEST_POSTGRES_URL` on a throwaway `postgres:17` | 242 tests, OK, 7 skipped |
| `test_seed`, `test_learning_review`, `test_authoring_read_api` on PostgreSQL alone | 36 tests, OK, 1 skipped (`sqlite_only` command test) |
| `npm run check:client`, `npm run typecheck`, `npm test`, `npm run build` (in `apps/`) | OK, OK, 7 files 62 tests OK, OK |

Smoke test of the real process (seed in the session scratchpad, deleted afterwards):

```text
python -m tests.seed --output …/smoke/seed      # {"manifest": "…/smoke/seed/seed.json"}
ALM_STORE=…/alm.sqlite ALM_POLICY_DIR=…/policies … python -m services.authoring_api --port 58011
GET /health                             -> {"status":"ok"} 200
GET /contexts/architecture-authoring    -> {"error":"unauthenticated","detail":"Authentication required",…} 401
GET /openapi.json                       -> 200
without ALM_STORE/ALM_POLICY_DIR        -> API not started: Authoring modules need ALM_STORE and ALM_POLICY_DIR (exit 2)
ALM_STORE=…/missing.sqlite              -> API not started: ALM_STORE names no existing SQLite database (exit 2); no file created
```

Signed-in reads through the real Keycloak were **not verified** in this chat.
Signed-in reads are covered by the in-memory provider of the tests.

Acceptance tests by name (`tests/services/test_authoring_read_api.py`, each also
on PostgreSQL as `AuthoringReadApiTestPostgreSQL`):

- Parity with the CLI. `test_context_summary_matches_cli_show`,
  `test_pending_proposals_match_cli_show_and_the_decide_preview` (refs equal the
  `AWAITING_DECISION` proposals of `show`; proposal and candidates equal what
  `decide` prints before `CONFIRM`, answered `no`; key equals the stored
  `reviewPayloadKey`), `test_project_inspection_matches_cli`,
  `test_approved_project_syllabus_matches_cli`,
  `test_release_inspection_matches_cli_show_release`. `test_refusals_match_the_cli`:
  403/422/409/422 where the CLI exits 2.
- Learner redaction. `test_a_learner_only_subject_gets_the_show_redaction`: same
  entities as CLI `show` for `learner`, only `ExecutionContext` and the
  learner's own `Participant`, empty pending list. Also
  `PendingProposalsTest.test_a_learner_only_subject_sees_no_proposal_as_in_show`.
- Unavailable context. `test_a_context_whose_policy_file_is_not_installed_is_unavailable`:
  all five endpoints answer 404 `context_unavailable` for `architecture-delivery`,
  and so does an unknown context; the CLI with the installed policy exits 2. After
  the preview file is copied into the policy directory, the summary is 200 and
  equals CLI `show --policy <preview>`. Also `PolicyDirectoryTest` and
  `ContextServicesTest`.
- Never writes. `test_endpoints_never_write`: `LearningStore.table_digests()`
  (row count and SHA-256 of every table) is unchanged after every endpoint for
  both subjects, in four contexts including the unavailable and unknown ones,
  and after an anonymous call. Also
  `PendingProposalsTest.test_reading_pending_proposals_writes_nothing`.
- OpenAPI and client. `test_snapshot_lists_the_skeleton_and_read_only_authoring_endpoints`,
  `test_every_error_response_documents_the_error_body`; `npm run check:client`.

CI on `69c4689` (Ubuntu, Python 3.11, Node 22.22.2): push run
[42596826087](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42596826087)
and pull_request run
[42596858705](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42596858705):
`generated-contracts`, `authoring-architecture`, `store-backends` (PostgreSQL 17
service, now including the S05 modules), `api-skeleton`, `front-end`,
`offline-evaluation` all pass. The commit that adds this handoff triggers a new
CI run; its result is reported in the PR, not here.

## Acceptance items of #82

| Item | Status |
| --- | --- |
| Each endpoint has a parity test with the CLI | Done: five parity tests plus refusals, on both backends |
| A learner-only subject gets the same redaction as `show` today | Done: summary and pending list |
| A context whose policy file is not installed is reported as unavailable | Done: 404 `context_unavailable`; installing the preview makes it available without restart |
| Endpoints never write (database change counter unchanged) | Done: table digests unchanged |
| OpenAPI snapshot updated; client regenerated | Done, including `ErrorBody` for every error status (owner addition) |

## Findings (not changed in this PR)

1. **Opening an empty PostgreSQL store creates the tables.** On an empty schema,
   `LearningStore` creates the tables (`_open_postgresql`), so the first API read
   on an empty database writes the schema. For SQLite the API refuses a missing
   file. Opening a version-1 SQLite file would also migrate it. A read-only open
   mode in the store would close both cases.
2. **Policy change between resolution and read.** The API resolves the policy
   from the context's current `policies` reference. If an import is applied at
   that moment, `load_context` raises `ValueError('Context contract or trusted
   policy mismatch')`, which maps to 422 instead of 404 or 409. This is rare, and
   reloading resolves it.
3. **`show` reads without a read transaction** (unchanged CLI behaviour). The
   other reads use `read_transaction`. Entities are immutable versions, so every
   reference still resolves, but the owned proposals may be newer than the root.
4. **Pending list carries full payloads.** Every pending proposal comes with all
   its candidates (generated content included). S07 may want a summary list and a
   per-proposal detail route.
5. **The approved syllabus response is large.** `ApprovedSyllabus.source` is the
   whole Curator input (`LeadInput`), exactly as the CLI prints it. It is
   staff-only (content authority), but S09 may want a smaller view.
6. **Policy directory is parsed on every request.** That is O(files) per request.
   A cache keyed by file modification time could replace it when the number of
   files grows.
7. **Content-authority checks stay 422.** `Project authoring requires content
   authority` is a plain `ValueError` in `learning/projects.py`, as documented in
   S03, so a staff subject without that authority gets 422, not 403.
8. **Documented statuses are not checked against the code paths.** The OpenAPI
   test checks that every documented error uses `ErrorBody`. It does not check
   that a route cannot return an undocumented status, such as 502 from a read.
9. **Exact references in paths.** Ids with `:` are percent-encoded by the
   client. FastAPI decodes them, as the tests show with `quote(..., safe="")`.
   `openapi-fetch` path encoding in the browser is not verified until S07.
10. **The seed lives in `tests/`** because it reuses the test fixtures. It is not
    part of any production entry point. `python -m tests.seed` sets the three
    telemetry variables to off only when they are unset.
11. **Still open from Chat 12.** Finding 2 (unmapped login shows raw JSON),
    finding 6 (no favicon), finding 7 (session expiry in the UI, S07), finding 8
    (axe in S07).
12. **Roadmap baseline row.** Chat 12 finding 10 still applies, now extended:
    record S01–S05 as done. The web stack row would read "`services/` with
    FastAPI 0.141.1, Authoring API read modules; `apps/` npm workspace with React
    19, Vite 8, studio shell". This chat does not edit the roadmap.

## Open decisions

None blocked S05. S06 has no open decision listed in the roadmap.

## Next step

After the owner reviews and merges PR #83 (which closes #82): **S06 — Review
endpoints**, using the "Prompt for later steps" of the roadmap with `chat-13.md`
as the latest handoff. S06 should take `review_payload_key` from
`GET /contexts/{context_id}/pending-proposals` as the key a decision must carry.
