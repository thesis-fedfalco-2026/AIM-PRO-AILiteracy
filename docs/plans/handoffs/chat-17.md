# Chat 17 handoff — S09a course from an uploaded AIM-PRO model

Date: 9 November 2026. Base: `main` at `aa8f72e` (PR #95 merged). Step:
**S09a** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 4).
Issue: [#97](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/97).
Branch `feat/s09a-course-from-aimpro`, PR: see the end of this file.

No model call, no live run, synthetic data only. Local services used, all
started and stopped in this chat: a throwaway `postgres:17` container on
`127.0.0.1:55499` (random password) for the PostgreSQL test variants, and the
Keycloak of `compose.identity.yml` (throwaway secrets) for the browser tests.
No ALM metamodel, ALM store schema, realm file, identity map or AIM-PRO/jjodel
export changed.

## Objective

A teacher starts the build of a course by uploading an AIM-PRO model.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git log --oneline -3 origin/main` | `aa8f72e` (merge of #95), `ff20963`, `71e5841` |
| `gh pr list --state open` | #96 (owner answers of Chat 16, branch `docs/s08-owner-answers`, `b5860b1`) |
| `gh pr view 96` | `OPEN`, not merged |
| `unittest discover -q`, telemetry off (`LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false`) | 925 tests, OK, 172 skipped |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |

**Differences from the Chat 16 handoff.** PR #95 is merged as Chat 16 expected.
The owner answers that Chat 16 added after the merge are in PR #96, still open;
this branch starts from `main` and does not contain them. The working tree had
someone else's changes, as Chats 15 and 16 reported: `README.md` (3 lines) and
the untracked `docs/architecture/system-overview.md`,
`docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md` and
`examples/lpo-ai/`. They are not part of this PR and were left as they were.

A first run of the suite in this chat reported 2 failures and 5 errors, all in
`tests.test_telemetry`: it was started with `OTEL_SDK_DISABLED=true`, which the
documented command does not set. With the documented variables the suite
passes (row above).

## Owner decisions taken in this chat (9 November 2026)

Asked before any change; recorded in issue #97.

1. **Source preparation as a job** (owner answer 1 in PR #96): **a separate
   step**, not S09a. The Curator job of S09a is grounded by a query.
2. **Where a course starts**: the teacher **creates the course from the
   studio**, and **the API writes the course policy**, with this design
   (approved as proposed): an operator installs a course template
   (`ALM_COURSE_TEMPLATE`, read only for the API) naming the subjects who may
   create courses and the source scopes of a new course; `POST /courses` writes
   one new policy file granting the creator `ADMINISTRATOR` and
   `CONTENT_RESPONSIBLE` in that context only, and bootstraps the context; the
   API never changes an existing file; the same request returns the same course;
   adding other people and changing or revoking policies stay out of scope.
3. **Invalid file**: refused when it is not JSON, too large (10 MiB,
   configurable), not jjodel megamodel 1.0, its metamodels cannot be read, or the
   chosen scenario and competency catalogue cannot be resolved. Findings against
   the generated contracts do not refuse it.

Uploads go to the worker's `ALM_AIMPRO_EXPORTS` directory (owner answer 2 in
PR #96).

## Changes

| File | Content |
| --- | --- |
| `services/authoring_api/courses.py` | Module `courses`: `POST /courses`, `CourseTemplate`, `course_policy`; checks the creator, refuses an id used by a context or named by an installed policy, installs the policy file, bootstraps |
| `services/authoring_api/exports.py` | Module `exports`: `POST /contexts/{id}/aimpro-exports`; bounded body read, the checks of decision 3 with fixed reasons, a hidden temporary file while checking, `<sha256>.json` by hard link; `ExportReport` |
| `services/authoring_api/projects.py` | `POST /contexts/{id}/projects` (`init-authoring-project`) and `GET /contexts/{id}/designs/{design_id}/versions/{version}/syllabus` (`show-aimpro-syllabus`) |
| `services/api_common/contexts.py` | `PolicyDirectory.installed` and `install` (exclusive, all-or-nothing); `ContextServices.policy_of` and `bootstrap` |
| `services/api_common/settings.py`, `services/authoring_api/app.py` | `ALM_COURSE_TEMPLATE`, `ALM_AIMPRO_EXPORTS`, `ALM_API_EXPORT_MAX_BYTES`; both new modules registered and checked at start; API version 0.5.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | Regenerated |
| `tests/synthetic_worker.py` | Dev-only worker with the synthetic models of `tests/services/job_fixtures.py` |
| `apps/studio/src/features/build/` | `BuildPage` (upload with report, Curator job followed to its proposal, project initialization), `buildApi`, `BuildServices`, `projects.ts` (selected projects, current design) |
| `apps/studio/src/features/home/HomePage.tsx`, `features/course/CoursePage.tsx` | "Create a course"; course page links to the build page; "no syllabus yet" for the course's author |
| `apps/studio/src/App.tsx`, `main.tsx`, `routes.tsx`, `paths.ts`, `i18n/en.json`, `vite.config.ts` | Wiring, strings, `/courses` proxied to the API |
| `apps/e2e/build.spec.ts`, `e2e/stack/*`, `e2e/support.ts` | Browser acceptance; the stack runs the synthetic worker, an export directory and a course template; course policy files are removed before each test |
| `docs/architecture/role-applications.md` | "Course from an AIM-PRO model (S09a)"; D10 note on course policy files; configuration rows; browser tests; smoke test variables |
| `.github/workflows/aimpro-contracts.yml` | `store-backends`: `+ test_authoring_courses_api`; `api-skeleton`: `+ test_authoring_courses_api test_authoring_exports_api` |

## Verification

**Contract tests came first.** Written and run (failing) before the code:
`tests/services/test_authoring_courses_api.py`,
`tests/services/test_authoring_exports_api.py` and the new paths in
`tests/services/test_api_openapi.py`. The first run after the implementation:
29 tests, one error, in a test (it built the seed twice in one directory).
Two architecture tests then failed on the code: the new modules imported
`learning.store` (module rule 3); they now answer 409 with `HTTPException`.

| Check | Result |
| --- | --- |
| `unittest tests.services.test_authoring_courses_api` with `ALM_TEST_POSTGRES_URL` (throwaway container) | 19 tests, OK, none skipped |
| `unittest discover -q`, telemetry off, final tree | 955 tests, OK, 180 skipped (925 / 172 before; the new skips are the PostgreSQL variants of the course tests) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run generate:client`, `check:client`, `typecheck`, `test`, `build` (in `apps/`) | client regenerated; OK, OK, 112 tests OK (101 before), OK |
| `npm run test:browser` (local Keycloak, throwaway secrets) | 10 passed (2 sign-ins and 8 tests), 14.6 s; the stack ran the synthetic worker |
| `git diff --check` | exit 0 |

The first browser run found two real gaps: the studio's Vite proxy did not
forward `/courses` to the API, and the course page told a learner of a context
without a design that the course "has no syllabus yet" (the existing learner
test caught it). Both were fixed; the course page now shows that message only
to the context's author or administrator, with a unit test for each case.

**Mutations.** Seven temporary mutations, applied one at a time by a script
that restored each file:

| Mutation | Result |
| --- | --- |
| An upload is stored re-serialized, not as received | caught: `test_a_course_is_built_from_an_uploaded_model`, `test_a_file_under_the_export_name_with_other_bytes_is_never_replaced` |
| A refused upload leaves its temporary file | caught: `test_an_invalid_file_is_refused_with_its_reason_and_nothing_is_recorded` |
| Contract findings refuse the file | caught: `test_a_course_is_built_from_an_uploaded_model` and others |
| Any signed-in subject may create a course | caught: `test_only_a_creator_of_the_template_may_create_a_course` |
| An id named by an installed policy is taken over | caught: `test_an_id_named_by_an_installed_policy_is_refused` |
| An installed policy file is replaced | caught: `test_a_different_file_under_the_course_policy_name_is_never_replaced` |
| Project initialization skips its policy pre-check | not caught: the core already answers 403 to a subject outside the context. The pre-check was redundant and was removed; the route now calls the service exactly as the CLI does. A test now also checks the 403 of the syllabus read |

**Not verified.** The production worker running a real Curator job (a live
run). The upload and course creation on PostgreSQL through the browser (the
browser tests use SQLite; the API tests of `courses` run on both backends). A
concurrent creation of the same course by two requests at once (the code
handles it; no test makes the race happen).

## Acceptance items of #97

| Item | Status | Evidence |
| --- | --- | --- |
| Browser test: upload the synthetic AIM-PRO export, run the Curator job with the synthetic model, review and apply the syllabus, initialize the project | Done | `build.spec.ts` "a course is built from an uploaded AIM-PRO model"; in Python, `test_a_course_is_built_from_an_uploaded_model` runs the same cycle through the API and `tests.synthetic_worker` |
| An invalid file is refused with its reason; nothing is recorded | Done | `test_an_invalid_file_is_refused_with_its_reason_and_nothing_is_recorded`: nine files, each 422 with its reason; the export directory is empty (no temporary file), the ALM table digests are unchanged, no job is queued. Browser: `build.spec.ts` "an invalid file…" (export directory and database file unchanged) |
| The uploaded bytes are kept unchanged (digest test) | Done | `test_an_upload_is_stored_unchanged_under_the_digest_of_its_bytes`: CRLF line ends and trailing whitespace are kept byte for byte under `<sha256>.json`; the browser test compares the stored file's SHA-256 with the uploaded file's |
| A course created from the studio gets its own new policy file and a PREPARATION/DRAFT context; only listed creators may create one; existing policy files are never changed | Done | `test_authoring_courses_api.py` (both backends): the exact policy written, every other file's digest unchanged, the creator as only participant, the learner 403; refusals for non-creators, missing CSRF, existing contexts, ids named by an installed policy, a different file under the name, invalid ids; replay and interrupted creation |
| Full offline suite, `generate --check`, OpenAPI check; CI green | Done locally; CI below | see Verification |

## Findings (not changed in this PR)

1. **The course policy has one subject.** Nobody else can be added to a course
   from the studio; a co-teacher or a learner needs an operator to install a
   new policy version, and a context's `policies` reference cannot change
   today. Course membership is the next policy question.
2. **The policy directory is now written by the API process.** It needs write
   access to `ALM_POLICY_DIR`. A deployment that wants the directory read-only
   cannot select the `courses` module.
3. **The scenario is still a name.** The upload and the Curator take
   `scenario` and `competencies` model names (defaults `SCN01`,
   `elena_usecase_competencies`). A model without them is refused. When the
   scenarios change (D16), the defaults and the check change with them.
4. **The synthetic Curator ignores the uploaded content.** With the synthetic
   model the proposed syllabus is the fixture's, whatever export is uploaded;
   the browser test proves the flow, not the Curator's quality.
5. **The browser test uploads the reference export the fixtures use**
   (`docs/resources/aimpro-megamodel-2026-11-02.json`), the "synthetic AIM-PRO
   export" of the roadmap acceptance; there is no smaller synthetic export.
6. **No list of uploads or jobs.** The build page keeps the upload report and
   the job only while it is open; reloading it loses them (the job and the file
   remain; the proposal is in the inbox). Chat 16 finding 9 (no job list) still
   applies.
7. **A pending project proposal is not shown on the build page.** Until it is
   applied, the form is offered again; a second proposal with another request
   id would be possible. The inbox lists the pending one.
8. **Uploads are never removed.** As jobs (Chat 16 finding 10), the export
   directory only grows.
9. **The syllabus proposal has no teacher view of its own.** It shows the
   generic teacher view (summary, diagnostics in words, technical details).
   A syllabus view in words belongs with S09b/S09c.
10. **Still open from earlier chats.** Chat 16 findings 1–12 are unchanged
    except 3 (source preparation: owner decided, separate step) and 4 (export
    storage: done here).

## Open decisions

None blocked S09a. Proposed for the owner to record in the roadmap (a chat does
not edit it, working protocol rule 9):

- the three decisions above, with the course template design;
- a new step for **source preparation as a job** (owner answer 1 of PR #96):
  job kind `prepare-aimpro-syllabus-sources`, a final status for "completed
  without a proposal" in the job contract, and the teacher's choice of the
  prepared sources for the Curator job;
- course membership (finding 1).

Still open from the roadmap: D19, D21, G7 / D4.

## Next step

After the owner merges this PR (which closes #97) and PR #96: **S09b —
Progressive refinement with the agents**, whose acceptance is defined with the
owner when it starts; or the source-preparation step if the owner places it
first.
