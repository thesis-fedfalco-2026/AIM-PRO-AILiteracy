# Chat 16 handoff — S08 agent job worker

Date: 9 November 2026. Base: `main` at `06eba09` (PR #93 merged). Step: **S08**
of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 3). Issue:
[#94](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/94).
Branch `feat/s08-agent-job-worker`,
[PR #95](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/95):
`71e5841` (S08) and the commit that adds this file.

No model call, no live run, synthetic data only. Local services used, all
started and stopped in this chat: a throwaway `postgres:17` container on
`127.0.0.1:55499` (random password) for the PostgreSQL test variants, and the
Keycloak of `compose.identity.yml` (throwaway secrets) for the browser tests.
No ALM metamodel, ALM store schema, realm file, identity map or AIM-PRO/jjodel
export changed.

## Objective

Generation runs in a worker, outside HTTP requests, and reports progress.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git log --oneline -3 origin/main` | `06eba09` (merge of #93), `7382d35` (merge of #92), `1c4d817` |
| `gh pr list --state open` | none |
| `gh pr view 92` / `93` / `73` | `MERGED` (`7382d35`, `06eba09`, `f44062b`) |
| `git merge-base --is-ancestor 0d51f76 origin/main` | true: S07b (PR #90) is on `main` |
| `unittest discover -q`, telemetry off | 832 tests, OK, 142 skipped |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `ListAgents` | four other sessions, all idle; no other session worked in this tree |
| Tools | Python 3.12.7, Node 22.22.2, Docker 29.8.2 |

**Differences from the Chat 15 handoff.** Chat 15 predates PRs #92 and #93;
`git log` shows both merged, so S07, the teacher view, S07b and the owner's
answers on D18–D21 are on `main`. The working tree had someone else's changes:
`README.md` (3 lines) and the untracked `docs/architecture/system-overview.md`,
`docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md` and
`examples/lpo-ai/`, as Chat 15 reported. They are not part of this PR and were
left as they were.

Dependencies: S07b is merged. D14 (jobs store) is a proposed default that was
approved with the roadmap (PR #73). S08 depends on no open decision.

## Changes

| File | Content |
| --- | --- |
| `services/jobs/store.py` | `JobStore` (D14). A SQLite location is a file of its own, refused if it holds the ALM tables; on PostgreSQL the tables live in schema `jobs`. A job is keyed by (context, `request_id`): the same kind, command and subject under the same id return the same job, anything else raises `StateConflict`. `claim` takes the oldest `QUEUED` job (`FOR UPDATE SKIP LOCKED` on PostgreSQL, `BEGIN IMMEDIATE` on SQLite). `transition` moves a job only from the given non-final statuses, so a final status never changes. Each status change writes a `status` event in the same transaction; `add_progress` stores the `alm.event/1` records of the run. One sequence covers both kinds of event and is the stream cursor |
| `services/jobs/kinds.py` | Command models and the registry: `generate-project-assessments`, `generate-project-teacher` and `generate-project-trainer` take a `GenerationCommand`; `generate-aimpro-syllabus` takes an `AimproExport` (file name and SHA-256), the source scope, and exactly one of `query` or `prepared_sources`. `Resources` holds the factories that only the worker has. An export that is missing or does not match its SHA-256 is refused |
| `services/jobs/worker.py` | `Worker.run_once` / `run` and `JobEventSink`; `outcome` maps a `LearningResponse` to a job status |
| `services/jobs/__main__.py` | `python -m services.jobs [--once] [--poll]`. `production_resources` reuses the CLI's factories and installs the provider-call listener |
| `services/authoring_api/jobs.py` | Module `jobs` with four routes (see the guide). Authorization runs in a dependency before the stream starts. The stream reads the job status before its events, so it ends at once for a job that has already ended |
| `learning/service.py` | `authorize_jobs` checks `propose` in the policy before it reads the context, so a non-participant gets `AuthorizationError`, not `StopIteration`. `authorize_abandonment` holds the check that `abandon_request` already made; `abandon_request` now calls it |
| `services/api_common/errors.py` | `stream_error_responses`: the error responses of a streaming route stay `application/json` `ErrorBody` in the OpenAPI |
| `services/api_common/settings.py`, `services/authoring_api/app.py` | Settings `ALM_JOBS_STORE` (required when the `jobs` module is selected), `ALM_API_JOB_POLL_SECONDS` (default 1) and `ALM_API_JOB_STREAM_SECONDS` (default 300); module registered; API version 0.4.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | Regenerated |
| `apps/e2e/stack/api.mjs` | Sets `ALM_JOBS_STORE` in `e2e/.state/` |
| `docs/architecture/role-applications.md` | "Implementation (S08)" under "Agent jobs"; configuration rows; `ALM_JOBS_STORE` in the smoke test |
| `.github/workflows/aimpro-contracts.yml` | `postgres` job: `+ test_job_store test_job_worker`; `api-skeleton` job: `+ test_authoring_jobs_api test_job_boundaries` |

**Job outcome.**

- `PROPOSED`: the response is a proposal; its references are linked.
- `ABANDONED`: the response is the core's abandoned failure.
- `FAILED`: any other failure response (its fixed core text becomes `detail`), or an unexpected exception (`Internal error`, logged by type only).
- `REJECTED`: `ContextUnavailable`, `AuthorizationError`, an invalid command (`Invalid job command`, with no input echoed), or another `ValueError` or `StateConflict`. These are host checks that run before any model; the core's fixed message becomes `detail`.

## Verification

**Contract tests came first.** These files were written before the code:

- `tests/services/test_job_store.py`
- `tests/services/test_job_worker.py`
- `tests/services/test_authoring_jobs_api.py`
- `tests/services/test_job_boundaries.py`
- the two new tests in `tests/test_learning_service.py`
- the job paths in `tests/services/test_api_openapi.py`

The first runs after the implementation found errors in the tests, not in the code:

- a frozen record used in a set;
- a policy model mutated in place;
- the context `DELIVERY` used without its policy being installed;
- a call count that included the generator's own two calls;
- `agent_system.registry` listed as a model client: it is configuration parsing, and the API process already imported it before S08.

One test failure was a real gap in the code: an `ErrorBody` documented as `text/event-stream`. It was fixed with `stream_error_responses`. Reviewing the stream code before publishing found a second gap: a client that reconnected after the final event of an ended job polled until the stream timed out. A test was added and the code fixed.

| Check | Result |
| --- | --- |
| `unittest tests.services.test_job_store tests.services.test_job_worker tests.test_learning_service` with `ALM_TEST_POSTGRES_URL` (throwaway container) | 114 tests, OK, none skipped; afterwards the test database holds only `public` |
| `unittest discover -q`, telemetry off, final tree | 925 tests, OK, 172 skipped (832 / 142 before; the new skips are the PostgreSQL variants) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run generate:client`, `check:client`, `typecheck`, `test`, `build` (in `apps/`) | client regenerated; OK, OK, 101 tests OK, OK |
| `npm run test:browser` (local Keycloak, throwaway secrets) | 8 passed (2 sign-ins and 6 tests), 13.5 s; the e2e API ran with the new `ALM_JOBS_STORE` |
| `git diff --check` | exit 0 |

**The tests can fail.** Six temporary mutations were made by a script (each file was restored afterwards). Each one made its test fail:

| Mutation | Failing test |
| --- | --- |
| The stream ignores that the job has ended | `test_the_event_stream_follows_the_job_and_carries_no_content` |
| `status` events carry the job command | same |
| A replay inserts a new job (the `ON CONFLICT` clause removed) | `test_a_replayed_request_id_returns_the_same_job_and_constructs_no_model` |
| The abandonment route skips the administrator check | `test_a_queued_job_is_abandoned_before_the_worker_takes_it` |
| The API module imports `services.jobs.worker` | `test_the_api_process_imports_no_model_client` |
| The worker reports `FAILED` for a proposal | `test_a_queued_evaluator_job_ends_as_a_pending_proposal_in_the_inbox` |

The first round let two mutations through: the stream mutation, because a `self.fail` inside the stream thread did not fail the test, and the abandonment mutation, because the core repeats the administrator check for a running job. Both tests were strengthened and the round was run again.

**CI on `71e5841`:** all seven jobs pass, in both the push run
[42651523932](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42651523932)
and the pull_request run
[42651571643](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42651571643).
The seven jobs are `generated-contracts`, `authoring-architecture`, `offline-evaluation`, `store-backends`, `api-skeleton`, `front-end` and `browser`.
In the pull_request run, `store-backends` (PostgreSQL service) ran 346 tests, OK, 7 skipped, in 493 s, and `api-skeleton` ran 128 tests, OK, 22 skipped. The commit that adds this file triggers another run, reported in the PR.

**Not verified.** The production worker (`python -m services.jobs`) running a real job: that builds real models, which would be a live run. The tests cover only the idle worker (`--once` with an empty queue builds nothing) and the missing-settings refusal. No manual end-to-end check with an API process and a worker process was made.

## Acceptance items of #94

| Item | Status | Evidence |
| --- | --- | --- |
| A queued Evaluator job ends as a pending proposal visible in the inbox | Done | `test_a_queued_evaluator_job_ends_as_a_pending_proposal_in_the_inbox`: `POST /jobs` returns `QUEUED`; the ALM tables are unchanged and no model is built; `worker.run_once()`; `GET` returns `PROPOSED`; `GET /pending-proposals` lists the new proposal first, next to the seed's pending one. The worker tests also check this on PostgreSQL |
| A replayed `request_id` returns the same job and constructs no model | Done | API: the same body before and after the run returns the same job; the worker finds nothing to run; one `authoring` build; the model call list is unchanged. Worker: an id the CLI already answered replays its result with no build (`test_a_request_id_already_recorded_by_the_cli_replays_its_result_without_a_model`) |
| An interrupted job can be abandoned by an administrator | Done | `test_an_interrupted_job_is_abandoned_by_an_administrator`: a `BaseException` raised during generation leaves the job `RUNNING` with its ALM request reserved. Without CSRF the abandonment is 403, for the learner 403, for a subject without `ADMINISTRATOR` 422; for the administrator it returns `ABANDONED`, and the ALM request holds the abandoned result. A second abandonment is 409. Statuses: `QUEUED`, `RUNNING`, `ABANDONED`. A queued job is also abandoned before it starts and never runs |
| The event stream carries no content (strict event log in tests) | Done | `EventSinkTest`: with the strict sink, a content event stops the run and is never stored; outside tests it is dropped. The API stream of a real Evaluator job holds neither the requirement nor any generated text; every `data` is a `StatusEvent` or an `Event`; resuming with `Last-Event-ID` works |
| The API process imports no model client (test) | Done | `test_the_api_process_imports_no_model_client`: a subprocess imports the app and builds it, then checks that none of these is loaded: `crewai`, `litellm`, `anthropic`, `openai`, `langfuse`, `mcp`, `dotenv`, `main`, the agent runtime, the orchestrator, the MCP runtime, `learning.__main__`, `services.jobs.worker`, `services.jobs.__main__`. A control test shows that the probe detects an import |
| Full suite, `generate --check`, OpenAPI check; CI green | Done | see Verification; CI runs 42651523932 and 42651571643 |

## Findings (not changed in this PR)

1. **Authoring generators emit no progress events.** `AuthoringDispatcher` and the generators call no `events.emit`. With synthetic models, an Evaluator or Curator job therefore streams `status` events only. In a real run the provider listener adds `provider.call` events. Per-step progress (for example "Evaluator draft", "Lead review") would need emits in `agent_system/authoring.py`, a core change.
2. **Lead rejection ends as `FAILED`, not `REJECTED`.** The role plan defines `REJECTED` as "host checks or Lead review rejected the output". The core returns the same `FAILURE` response for a Lead `REJECT` and for a provider error, so the worker cannot tell them apart. Telling them apart needs a structured failure code in the core.
3. **Kinds not covered.** These stay CLI commands:
   - `prepare-aimpro-syllabus-sources`: no model and no proposal; its result (`PreparedSources`) fits none of the six job statuses.
   - `generate-aimpro`: the older SCN01 teaching draft; it is not in the role plan's list.
   - `ask`: the learner request, which is S12.

   S09a may need source preparation from the studio. That needs a status or result for "completed without a proposal", a change to the job contract in the guide.
4. **Where AIM-PRO exports live.** Curator jobs name an export file in the worker's `ALM_AIMPRO_EXPORTS` directory by name and SHA-256. S09a (upload) needs to store uploads where the worker reads them, or choose another way.
5. **A crash window remains.** If the worker stops after the ALM request is finished but before the job is updated, the job stays `RUNNING`, and abandoning it is a 409 (the ALM request is no longer pending). No reconciliation (the job takes the ALM result) is implemented.
6. **A non-participant subject raises `StopIteration`** in `LearningService._context` (`next()` without a default). Existing routes answer 500 in that case. The job routes check the policy first, so they answer 403.
7. **Abandonment by a subject without `ADMINISTRATOR` is 422**, following the guide's convention for role checks that raise a plain `ValueError` (Chat 14 finding 3 has the same shape).
8. **The stream header is `Cache-Control: no-cache`**, set by FastAPI's SSE response, not `no-store` as the JSON reads use. The stream carries no content.
9. **No job list.** The studio will need a list of a context's jobs (S09a/S09c); S08 adds only reading one job.
10. **No retention.** Jobs and events are never deleted; old events of finished jobs keep accumulating.
11. **Every deployment that selects all modules now needs `ALM_JOBS_STORE`.** The guide, the e2e stack and the tests are updated. The owner test script in Chat 15 predates this: add `export ALM_JOBS_STORE=$SEED/jobs.sqlite`.
12. **Still open from earlier chats.** Chat 15 findings 2–12 and S07b findings 1–4 are unchanged.

## Open decisions

None blocked S08. For S09a, findings 3 and 4 may need an owner answer:

- a job outcome for source preparation;
- where uploaded AIM-PRO exports are stored for the worker.

Still open from the roadmap: D19, D21, G7 / D4.

## Next step

After the owner merges PR #95 (which closes #94): **S09a — Course from an
uploaded AIM-PRO model**, in a new chat with the roadmap's "Prompt for later
steps".
