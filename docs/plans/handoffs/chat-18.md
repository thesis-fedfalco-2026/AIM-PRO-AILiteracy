# Chat 18 handoff — S09a2 source preparation as a job

Date: 10 November 2026. Base: `main` at `07bcc57` (PRs #99 and #100 merged).
Step: **S09a2** of the [prototype roadmap](../prototype-roadmap.md) (D22).
Issue: [#101](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/101).
Branch `feat/s09a2-source-preparation`, PR: see the end of this file.

No model call, no live run, synthetic data only. One local service was started
and removed in this chat: a throwaway `postgres:17` container on
`127.0.0.1:55499` (random password) for the PostgreSQL variants. No ALM
metamodel, ALM store schema, jobs store schema, realm file, identity map or
AIM-PRO/jjodel export changed.

## Objective

A teacher has the sources of a course prepared, reviews them and decides
whether the Curator uses them. Nothing is used until the teacher accepts.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git log --oneline -3 origin/main` | `07bcc57` (merge of #100), `d4f1aac` (merge of #99), `55fbad2` |
| `gh pr list --state open` | none |
| PR #99 (D22–D25, S09a2 section) | merged |
| Studio-clarity PR (#100) | merged |
| `unittest discover -q`, telemetry off (`LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false`) | 956 tests, OK, 180 skipped |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 114 tests OK |

**Differences from the Chat 17 handoff.** PR #98 (S09a), #99 and #100 are all
on `main`; the suite grew from 955/180 to 956/180 with #100. The working tree
had someone else's changes as before: `README.md` and the untracked
`docs/architecture/system-overview.md`, `docs/plans/handoffs/chat-01.md`,
`docs/plans/sequential-chat-plan.md` and `examples/lpo-ai/`. They are not part
of this PR and were left as they were.

## Owner decisions taken in this chat (10 November 2026)

Asked before any change; recorded in issue #101.

1. **Two jobs: discovery, then preparation.** A `SourcePlan` names exact
   excerpts (id, SHA-256, purpose, limitations) that a teacher cannot know
   before searching, and the studio never calls the corpus. A model-free
   discovery job runs the teacher's queries and records what they found (a new
   core operation, in the ALM requests store, replayed without a new search);
   the teacher picks excerpts; the preparation job (core unchanged) fetches
   them exactly. The `SourcePlan` contract is unchanged.
2. **The acceptance is recorded in the jobs store.** A preparation job ends
   `AWAITING_CHOICE`; the teacher moves it to `ACCEPTED` or `DECLINED`. The API
   and the worker refuse a Curator job naming a preparation that is not
   accepted. The CLI `--prepared-sources` stays an operator path without
   acceptance.
3. **A minimal job list is in scope** on the build page.
4. **Coverage requirements**: an optional form guided by the uploaded export
   (targets, practices and field texts listed by the API).
5. **Acceptance list** of the roadmap confirmed as proposed.

Defaults taken without a question, stated in the guide: only the subject who
prepared the sources chooses them (the core already binds a Curator run to the
preparation of the same subject); the studio sets `min_resources` and
`max_documents_per_resource` to the distribution the teacher picked; a choice
is final.

## Changes

| File | Content |
| --- | --- |
| `aimpro/source_selection.py` | `SourceDiscovery` (scope, 1–20 unique queries); `discover()` factored out of `collect_sources` (same results and trace) |
| `aimpro/source_service.py` | `DiscoveredSources`, `discover_sources` (authority, scope and draft before the client; reservation; replay; fixed failure text), `source_request` (a subject's completed discovery or preparation, else `None`) |
| `learning/service.py`, `learning/__main__.py` | `discover_aimpro_syllabus_sources`, `aimpro_source_request`; CLI `discover-aimpro-syllabus-sources --discovery FILE --request-id` |
| `services/jobs/store.py` | Statuses `COMPLETED`, `AWAITING_CHOICE`, `ACCEPTED`, `DECLINED`; `FINAL`, `ENDED`, `CHOICES`; only a choice ends `AWAITING_CHOICE`; `list(context_id, limit)`. Status is a text column: no schema change |
| `services/jobs/kinds.py` | `DiscoveryJob`, `PreparationJob` (plan must name the export's SHA-256); `Resources.search_client`; `unaccepted_sources()` |
| `services/jobs/worker.py`, `services/jobs/__main__.py` | Outcomes `COMPLETED`, `AWAITING_CHOICE`; Curator jobs on unaccepted sources `REJECTED` before any model; the production search client |
| `services/authoring_api/jobs.py` | `GET /contexts/{id}/jobs` (`JobList`), `POST …/jobs/{request_id}/choice` (`SourceChoice`), 409 on queuing a Curator job on unaccepted sources; streams end once the run has ended |
| `services/authoring_api/sources.py` (new module `sources`) | `GET …/source-discoveries/{request_id}`, `GET …/source-preparations/{request_id}` with excerpts, licence and verdict |
| `services/authoring_api/exports.py` | `GET …/aimpro-exports/{sha256}/targets` (`ExportTargets`) |
| `services/authoring_api/app.py` | module `sources` registered; API version 0.6.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | Regenerated |
| `apps/studio/src/features/course-build/` | `JobsList.tsx`, `SourcesStep.tsx` (search, pick with purpose and limitations, coverage requirements, review, accept or decline), `parts.tsx` (shared form parts, `useFollowedJob`), `BuildPage.tsx` (Curator from accepted sources or a query; steps renumbered 1–4), `buildApi.ts` |
| `apps/studio/src/i18n/en.json` | `build.jobs`, `build.sources`, Curator grounding strings; intro and "not kept" texts |
| `tests/test_source_discovery.py`, `tests/services/test_authoring_sources_api.py` | New |
| `tests/services/test_job_store.py`, `test_job_worker.py`, `job_fixtures.py`, `test_api_openapi.py`, `test_api_contexts.py` | New statuses, kinds, synthetic search client, contract assertions |
| `apps/studio/test/build.test.tsx`, `apps/e2e/build.spec.ts` | Unit tests and the browser acceptance test |
| `apps/e2e/support.ts`, `apps/e2e/stack/paths.mjs`, `apps/e2e/stack/api.mjs` | The jobs of an earlier test are deleted before each test, as the database is restored |
| `docs/architecture/role-applications.md`, `docs/aimpro/selected-sources.md` | "Source preparation as a job (S09a2)", job contract, routes, browser test row; discovery in the source guide |
| `.github/workflows/aimpro-contracts.yml` | `+ tests.test_source_discovery` (job with `test_source_selection`), `+ tests.services.test_authoring_sources_api` (`api-skeleton`) |

## Verification

**Contract tests came first.** `tests/test_source_discovery.py`,
`tests/services/test_authoring_sources_api.py`, and the new cases in
`test_job_store`, `test_job_worker` and `test_api_openapi` were written and run
before the implementation: 75 tests, 2 failures and 41 errors. Two contract
assertions (`REGISTRY.names`, the job-kind mapping and status enum of the
snapshot) were then updated for the new module, kinds and statuses. One store
test of mine contradicted the stricter rule chosen (only a choice ends
`AWAITING_CHOICE`) and was corrected.

| Check | Result |
| --- | --- |
| `unittest discover -q`, telemetry off, final tree | 1004 tests, OK, 189 skipped (956 / 180 before; the new skips are PostgreSQL variants) |
| `unittest tests.services.test_job_store tests.services.test_job_worker` with `ALM_TEST_POSTGRES_URL` (throwaway container) | 85 tests, OK, none skipped |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `tests.services.test_job_boundaries` (the API imports no model client) | OK |
| `npm run generate:client`, `check:client`, `typecheck`, `test`, `build` (in `apps/`) | regenerated; OK, OK, 117 tests OK (114 before), OK |
| `npx playwright test --list` | 11 tests in 5 files (the new one included); compiles |
| `git diff --check` | exit 0 |

**Mutations.** Six temporary mutations, each applied and restored by a script:

| Mutation | Result |
| --- | --- |
| The worker skips the acceptance check | caught: `test_a_curator_job_never_uses_prepared_sources_that_were_not_accepted`, `test_sources_accepted_by_another_subject_are_not_used` |
| The API skips the acceptance check | caught: `test_a_curator_job_on_sources_not_accepted_is_refused_and_nothing_is_queued` |
| A preparation awaiting the choice counts as accepted | caught by both tests above |
| Another subject's accepted preparation counts | caught: `test_sources_accepted_by_another_subject_are_not_used` |
| Any subject may make the choice | caught: `test_a_preparation_of_another_subject_is_not_chosen_by_this_one` |
| A discovery replay searches again | caught: `test_a_replayed_request_id_returns_the_same_discovery_without_a_search` and one more |

**Not verified locally.** The browser tests (`npm run test:browser`): ports
`58000` and `58001` were held by the owner's demo stack of the morning trial
(an API and a Vite server started at 09:37), which this chat did not stop; the
CI job `browser` runs them (result in the PR). A real discovery and preparation
on the `wp3` corpus through MCP (the worker's production search client is the
CLI's, unchanged; no live run). The coverage-requirement form in a browser
(unit-tested only; the browser test uses no requirement). A preparation with the
LPO export.

**First CI run** on `d2951af` (push run
[42803800139](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42803800139),
pull_request run
[42803839640](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42803839640)):
every job passed except `browser`. The new S09a2 browser test **passed**; two
S09a tests failed. (1) `getByLabel('Source scope')` also matched the new
"Source scope to search" (Playwright matches substrings): the S09a test now asks
for the exact label. (2) The browser stack restored the database before each
test but not the jobs database, so the preparation accepted by the S09a2 test
was still offered to the Curator of the next test on the same course id: the
per-test fixture now deletes the jobs too. The result of the next run is in
the PR.

## Acceptance items of #101

| Item | Status | Evidence |
| --- | --- | --- |
| Browser test: prepare sources with the synthetic retrieval, review them, accept them, run the Curator on them, review and apply the syllabus | Written; CI | `build.spec.ts` "a syllabus is built on sources the teacher prepared and accepted"; the same cycle through the API and `tests.synthetic_worker`: `test_a_syllabus_is_built_on_sources_the_teacher_accepted` |
| Sources not accepted are never used by a Curator job (test) | Done | worker: awaiting, declined, CLI-only, a discovery, a missing id, another subject's: `REJECTED` with no ALM request and no model; API: 409 and nothing queued |
| A replayed request id returns the same preparation and runs no retrieval again | Done | `test_a_preparation_already_recorded_under_the_request_id_runs_no_retrieval` (no client built, no search, no fetch); API: `test_a_replayed_preparation_returns_the_same_job_and_preparation`; core: discovery replay test |
| Contract tests first; suite, generate check, OpenAPI check; CI green | Done locally; CI below | see Verification |

## Findings (not changed in this PR)

1. **A preparation is tied to the course version.** The core refuses prepared
   sources whose context version differs from the current one ("Prepared
   sources are stale…"). Anything applied to the course between the
   preparation and the Curator run, a syllabus included, makes the teacher
   prepare again; the Curator job then ends `REJECTED` with that reason.
2. **The CLI does not consult the teacher's choice.** `generate-aimpro-syllabus
   --prepared-sources` uses any completed preparation of the same subject, as
   before (owner decision 2). Enforcing the choice in the core would need an
   ALM record of it.
3. **The upload is still not listed.** A preparation needs the upload of the
   same page visit (the file uploaded again is recognized). Discoveries,
   preparations and Curator jobs are listed and can be resumed (Chat 17
   finding 6 is half solved).
4. **The synthetic retrieval returns the same single excerpt for every query.**
   The tests prove the flow, not the quality of a selection.
5. **Excerpt texts are stored in the ALM requests table** for every discovery
   (all excerpts found) and preparation. Like uploads and jobs, nothing is ever
   removed.
6. **The synthetic Curator covers no coverage requirement**, so a Curator run
   on a preparation with requirements fails with the synthetic models; the
   real Curator must cover them (the core checks it).
7. **Prompt size with LPO is not bounded by this step.** Prepared sources send
   only the chosen excerpts, but the LPO prompt is dominated by the export
   itself (about 562k characters in the trial). Not measured here.
8. **Licence verdicts are shown as the corpus records them.** The set of
   `licence_verdict` values in the WP3 corpus was not checked; a missing
   verdict is shown as "no verdict, check it before use".
9. **A choice is final.** Accepted sources cannot be withdrawn; the teacher can
   prepare again and use another preparation.
10. **Jobs of other subjects are listed** to everybody who may propose in the
    course, with their kind and status (as `GET …/jobs/{id}` already returned
    them in S08); only the teacher's own jobs offer actions.
11. **Still open:** the 24-unit caps in `aimpro/didactic.py` and
    `aimpro/teacher_contracts.py` (S09c); Chat 17 findings 1–3, 5, 7–10.

## Open decisions

None blocked S09a2. Proposed for the owner to record in the roadmap (a chat
does not edit it, working protocol rule 9):

- the four decisions above (two jobs; acceptance in the jobs store, CLI path
  unchanged; minimal job list; coverage requirements from the export);
- S09a2 marked done with this PR, and its acceptance list as confirmed.

Still open from the roadmap: D19, D21, D25, G7 / D4.

## Next step

After the owner merges this PR (which closes #101): **S09b — Progressive
refinement with the agents**, whose acceptance is defined with the owner when
it starts (ask before writing the issue). Then **S09c**.
