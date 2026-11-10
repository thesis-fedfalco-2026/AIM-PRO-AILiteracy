# Chat 19 handoff — S09b progressive refinement of the syllabus

Date: 10 November 2026. Base: `main` at `d57fe13` (PR #103, S09a2, merged).
Step: **S09b** of the [prototype roadmap](../prototype-roadmap.md) (D18).
Issue: [#104](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/104).
Branch `feat/s09b-syllabus-refinement`, PR: see the end of this file.

No model call, no live run, synthetic data only. No ALM metamodel, ALM store
schema, jobs store schema, realm file, identity map or AIM-PRO/jjodel export
changed. The syllabus payload (`SyllabusArtifact`, a JSON text inside an ALM
`Resource`) gains optional fields, omitted when absent.

## Objective

A teacher refines the syllabus step by step with the agents. The Curator's
output and the teacher's edits stay proposals that a human decides and applies.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git log --oneline -3 origin/main` | `d57fe13` (merge of #103), `db0b48a`, `d2951af` |
| `gh pr list --state open` | none |
| PR #103 (S09a2) | merged 10 November 2026, 11:26 UTC |
| Roadmap PR recording the S09a2 decisions | none open; the roadmap's last change is `166aec2` (#99) |
| `unittest discover -q`, telemetry off | 1004 tests, OK, 189 skipped (as Chat 18) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 117 tests OK (as Chat 18) |

The working tree had someone else's changes as before (`README.md` and the
untracked `docs/architecture/system-overview.md`, `docs/plans/handoffs/chat-01.md`,
`docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/`); they are not part of
this PR. The owner's demo stack still held ports 58000 and 58001; it was not
stopped.

## Owner decisions taken in this chat (10 November 2026)

Asked before the issue was opened; recorded in issue #104.

1. **Pairing key: the learning target.** Units are paired on
   `source_target_id`; several units on one target are paired in their order;
   the extra units are added or removed.
2. **The Curator holds the conversation** (no separate Design Agent). One
   reason per revision request; the next Curator job receives the previous
   proposal and **all the reasons of the chain**, first to last.
3. **A manual edit is complete** (every field, add, remove and reorder units),
   recorded as a new proposal by the teacher, and must pass **all the checks**
   of a generated syllabus. The agent's review of an edit is optional and does
   not block; without it the edit is declared "edited by the teacher, not
   reviewed by the agent", and the teacher may approve and apply it.
4. **A revision on prepared sources reuses the accepted preparation** while the
   course version is unchanged; otherwise the sources are prepared again.
5. **The acceptance list** was confirmed as proposed.

Defaults taken without a question, stated here and in the guide:

- A refinement (revision or edit) reuses the **whole input of the proposal it
  refines**, the source snapshot with its excerpts, whether prepared or
  retrieved by a query: nothing is searched or fetched again. "Course version
  unchanged" is read as: the course is still at that proposal's step, its base
  version, or the version its own application produced. So an applied syllabus
  can be edited until something else is applied.
- A revision needs a `REQUEST_REVISION` decision on the latest revision of the
  proposal; the decision's reason is the new turn. An applied syllabus cannot
  be revised by the Curator (a decision on an applied proposal is not a
  revision request), only edited (finding 2).
- An edit inherits the revision reasons of the proposal it edits; it adds none.
- The edited proposal and the one it edits both stay pending; the teacher
  decides each.
- The optional agent review of an edit is **not implemented** (it is not in the
  acceptance list); proposed below.

## Changes

| File | Content |
| --- | --- |
| `aimpro/syllabus.py` | `SyllabusRevision` (previous draft, reasons); `generate(..., revision=)` adds `AIMPRO_SYLLABUS_REVISION` to the Curator prompt and `previous_syllabus`, `teacher_reasons` to its DATA; the prompt without a revision is unchanged |
| `aimpro/syllabus_state.py` | `SyllabusArtifact`: optional `review`, `revises`, `revision_reasons`, `edited_by` (omitted when absent; `review` absent exactly when `edited_by` is set); `candidates(..., revises=, revision_reasons=, edited_by=)`; `ProposedSyllabus`, `syllabus_artifact`, `proposed` (a proposal's syllabus at any status), `NoSyllabus`; the resolver checks the review only when there is one |
| `aimpro/syllabus_compare.py` (new) | `compare(before, after)`: `SyllabusComparison` with `UnitComparison` rows (`ADDED`, `REMOVED`, `CHANGED`, `UNCHANGED`, changed fields), title, gaps and order |
| `aimpro/syllabus_refinement.py` (new) | `revise_syllabus` (request check, step check, replay, fixed failure text), `edit_syllabus` (one write transaction, same checks, no model) |
| `learning/service.py`, `learning/__main__.py` | `revise_aimpro_syllabus`, `edit_aimpro_syllabus`, `aimpro_syllabus_proposal`; CLI `revise-aimpro-syllabus --proposal ID`, `edit-aimpro-syllabus --proposal ID --draft FILE` |
| `services/jobs/kinds.py` | `RevisionJob`, kind `revise-aimpro-syllabus` |
| `services/authoring_api/syllabus.py` (new module `syllabus`), `app.py` | `GET …/syllabus-proposals/{proposal_id}` (`SyllabusProposalView`), `POST …/syllabus-edits` (`SyllabusEdit` → `EditedSyllabus`); API version 0.7.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | Regenerated |
| `apps/studio/src/features/review/` | `syllabus.ts` (units in words, comparison rows, editor helpers), `SyllabusView.tsx`, `RevisionStep.tsx`, `SyllabusEditPage.tsx` (route `…/review/{proposal}/edit`); `ProposalPage.tsx` shows the syllabus view instead of the generic teacher view for a syllabus proposal; `TeacherView.tsx`: the issues section is its own `Issues` component; `reviewApi.ts`, `paths.ts`, `routes.tsx` |
| `apps/studio/src/features/course/` | `course.ts`, `CoursePage.tsx`: the syllabus in use in the structure section |
| `apps/studio/src/features/course-build/` | `buildApi.ts` (`queueRevision`), `JobsList.tsx` (revision kind label) |
| `apps/studio/src/i18n/en.json` | `review.syllabus.*`, `review.teacher.titleSyllabus`, `course.syllabus.*`, `build.jobs.kind.revision` |
| `tests/test_syllabus_refinement.py`, `tests/services/test_authoring_syllabus_api.py` | New |
| `tests/syllabus_fixtures.py`, `tests/services/job_fixtures.py` | `revised_syllabus()`; the synthetic Curator returns it for a revision prompt (so `tests.synthetic_worker` does too); `revision_job()` |
| `tests/services/test_job_worker.py`, `test_api_openapi.py`, `test_api_contexts.py` | Revision jobs; new kind, routes and module in the contracts |
| `apps/studio/test/syllabus-fixture.ts`, `syllabus-model.test.ts`, `syllabus.test.tsx`, `course-model.test.ts` | Unit and page tests |
| `apps/e2e/refinement.spec.ts` | The browser acceptance test |
| `docs/architecture/role-applications.md` | "Syllabus refinement (S09b)", the job kind, the browser test row |
| `.github/workflows/aimpro-contracts.yml` | `+ tests.test_syllabus_refinement`, `+ tests.services.test_authoring_syllabus_api` |

## Verification

**Contract tests.** For the worker, the API and the client the tests came
first: the revision job tests failed with "Unknown job kind" (4 failures), the
API tests failed before the module existed (7 of 8; the stale-revision test
only needs the job kind), the OpenAPI and registry contracts failed (9) until
the module, the snapshot and the client were regenerated. **For the core this
was not the case**: `aimpro/syllabus_compare.py` and
`aimpro/syllabus_refinement.py` were written before
`tests/test_syllabus_refinement.py`, which passed on its first run; the
mutations below check that those tests are not vacuous.

| Check | Result |
| --- | --- |
| `unittest discover -q`, telemetry off, final tree | 1034 tests, OK, 192 skipped (1004 / 189 before; the 3 new skips are the PostgreSQL variants of the revision jobs) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `tests.services.test_job_boundaries` (the API imports no model client) | OK |
| `npm run generate:client`, `check:client`, `typecheck`, `test`, `build` (in `apps/`) | regenerated; OK, OK, 132 tests OK (117 before), OK |
| `npx playwright test --list` | 12 tests in 6 files (the new one included); compiles |
| `git diff --check` | exit 0 |

**Mutations.** Seven temporary mutations, each applied and restored by a script,
against `tests.test_syllabus_refinement`, `tests.services.test_authoring_syllabus_api`
and the worker's `RevisionJobTest`:

| Mutation | Result |
| --- | --- |
| Units paired by their key instead of their target | caught: `test_a_removed_target_comes_last_and_reordering_is_reported` and the revision comparisons |
| Only the last reason reaches the Curator | caught: `test_the_whole_chain_of_reasons_reaches_the_next_revision` |
| The course step is not checked | caught: both stale tests and `test_an_applied_edit_resolves_as_the_course_syllabus_and_can_be_refined_again` |
| A revision without a revision request | caught: `test_a_revision_needs_a_revision_request_and_runs_no_model_without_one` |
| The revision is not given to the Curator | caught: the reason-in-prompt tests (core, worker, API) |
| An edit skips `checked_syllabus` in `edit_syllabus` | not caught, and equivalent: `candidates()` runs the same checks in the same transaction, which then rolls back |
| An edit skips the checks in both places | caught: `test_an_edit_passes_the_same_checks_as_a_generated_syllabus` |

**Not verified locally.** The browser tests (`npm run test:browser`): ports
58000 and 58001 were held by the owner's demo stack, which this chat did not
stop; the CI job `browser` runs them (result in the PR). No real Curator
revision (no model call). The editor with the LPO export (many targets).

## Acceptance items of #104

| Item | Status | Evidence |
| --- | --- | --- |
| A teacher view in words for every syllabus proposal | Done; browser test in CI | API `test_a_syllabus_proposal_is_read_in_words`, `test_excerpts_of_prepared_sources_carry_their_purpose_and_limitations`; studio `syllabus-model.test.ts`, `syllabus.test.tsx` "is shown in words"; `refinement.spec.ts` |
| Compared with the course's syllabus, units paired by target, with changed fields; several units on one target; a course without a syllabus | Done | `SyllabusComparisonTest` (5 tests), API `test_each_applied_step_becomes_the_course_syllabus_it_is_compared_with` |
| A revision request carries its reason to the next Curator generation; compared with the previous proposal | Done | `test_a_revision_request_carries_its_reason_to_the_curator`, `test_the_whole_chain_of_reasons_reaches_the_next_revision`, worker `test_a_revision_job_gives_the_reason_to_the_curator_and_proposes_a_revised_syllabus`, API `test_a_revision_request_reaches_the_curator_and_is_compared_with_the_previous_proposal` |
| A teacher's edit is a new proposal by that teacher, compared with the one it edits | Done | `test_an_edit_is_a_new_proposal_by_the_teacher_not_reviewed_by_the_agent`, `test_an_edit_passes_the_same_checks_as_a_generated_syllabus`, API `test_an_edit_is_recorded_as_a_new_proposal_by_the_teacher` |
| After each applied step the course overview shows the applied syllabus | Done; browser test in CI | `course-model.test.ts`, `refinement.spec.ts` (two applied steps) |
| Contract tests first; suite, generate check, OpenAPI check; CI green | Partly (core tests not first, see above); CI below | see Verification |

## Findings (not changed in this PR)

1. **Reordering units on one target shows as changes, not as a move.** With
   the pairing chosen (target, then order), swapping two units of the same
   target pairs each with the other: both are "changed". A move across targets
   is reported as "the order of the units changes". The browser test edits a
   title instead of reordering for this reason.
2. **An applied syllabus cannot be revised by the Curator**, only edited: a
   revision needs a `REQUEST_REVISION` decision, and a decision on an applied
   proposal is not one (it would set the applied proposal back to `DRAFT`). A
   Curator turn on the syllabus in use needs either a revision job that carries
   its own reason or a new decision kind: an owner decision.
3. **The optional agent review of a teacher's edit is not implemented.**
   Proposed: a job `review-aimpro-syllabus` that runs the review agent on an
   edited proposal and records a new proposal with the verdict (the payload
   with a review is another payload), or a review record beside it. Owner
   decision on the form, and a model call.
4. **A refinement never fetches sources again.** The excerpts of the first
   proposal are those of every refinement in the chain; an edit can only cite
   them. Citing other sources needs a new preparation and a new Curator job.
5. **Two pending syllabus proposals may coexist** (an edit and the proposal it
   edits, or two revisions). Applying one makes the others stale for
   application and for refinement.
6. **The revision job carries no client-visible link to the decision**: the
   worker reads the latest decision of the proposal when it runs. A second
   decision recorded between queueing and running would change the reason.
7. **Coverage entries are not editable in the editor.** They are kept while a
   unit stays on its target and dropped when it moves; a syllabus on prepared
   sources with coverage requirements then fails the checks with the core's
   fixed reason.
8. **The editor and the view show what the source snapshot holds.** Targets of
   the current syllabus that the proposal's source does not have are shown by
   id.
9. **Still open:** the 24-unit caps in `aimpro/didactic.py` and
   `aimpro/teacher_contracts.py` (S09c); Chat 18 findings 1–3 and 5–10.

## Open decisions

None blocked S09b. Proposed for the owner to record in the roadmap (a chat does
not edit it, working protocol rule 9):

- the S09a2 decisions and S09a2 marked done (proposed in the Chat 18 handoff;
  no roadmap PR records them yet);
- the four S09b decisions above, and S09b marked done with this PR;
- findings 2 and 3 (a Curator revision of the applied syllabus; the optional
  agent review of an edit) as decisions for S09c or a later step.

Still open from the roadmap: D19, D21, D25, G7 / D4.

## Next step

After the owner merges this PR (which closes #104): **S09c — Rubrics,
assessments and content from the studio**, whose acceptance is in the roadmap;
it includes the 24-unit caps, with the owner.

## PR and CI

PR [#105](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/105),
commit `e6ef3b3` (the change) and this handoff update. CI on `e6ef3b3`, push run
[42816541682](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42816541682)
and pull_request run
[42816584870](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42816584870):
all 14 jobs passed, `browser` included (the new `refinement.spec.ts` with the
synthetic worker) and `store-backends` (the PostgreSQL variants of the
revision jobs).
