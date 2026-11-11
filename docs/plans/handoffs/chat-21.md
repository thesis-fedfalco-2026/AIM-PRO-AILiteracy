# Chat 21 handoff — S09c: the review of the Evaluator, Teacher and Trainer drafts, and 96-unit caps

Date: 10–11 November 2026. Base: `main` at `cf2e9fe` (PR #109, the roadmap record of D30–D33, merged on
top of PR #108).
Step: **S09c** of the [prototype roadmap](../prototype-roadmap.md), first part (split with the owner, below).
Issue: [#110](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/110).
Branch `feat/s09c-generator-review`, PR: see the end of this file.

No ALM metamodel, ALM store schema, jobs store schema, realm file, identity map or AIM-PRO/jjodel export
changed. No model was called and no live run was made. The owner's demo stack was not touched.

## Objective

Let the generators of the rest of the authoring cycle (Evaluator, Teacher, Trainer) take a whole syllabus, and
apply D30 to their review, before the studio offers their forms (S09c2).

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git log --oneline -3` | `0b7fed9` on `docs/roadmap-chat20-review-decisions` (PR #109 open, CI green); the branch of this step starts from `main` at `cf2e9fe` after the owner merged #109 |
| `unittest discover -q`, telemetry off | 1052 tests, OK, 194 skipped (as Chat 20) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 134 tests OK (as Chat 20) |

The working tree had someone else's changes as before (`README.md` and the untracked
`docs/architecture/system-overview.md`, `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`,
`examples/lpo-ai/`); they are not part of this PR.

**What was found** (read before asking the owner):

- The proposal kinds of the synthetic seed are eight: the Curator syllabus, the project initialization, the
  assessment (one applied, one pending), the teacher content, the trainer content, the completion rules, the
  release and the delivery import (one applied, one pending). The studio's teacher view in words covers the
  syllabus and the assessment; the others show "other proposal", and the teacher and trainer material texts
  (`Resource`) are not shown. The teacher view exists only for pending proposals.
- The review of the generators lost its verdict, as the Curator's did before Chat 20: `checked_verdict`
  (`aimpro/generators.py`) raised `ReviewError('Authoring output did not pass separate Lead review')` and
  dropped the verdict; the trace span was updated only after an `ACCEPT`; `generate_project`
  (`learning/generation.py`) caught every exception and recorded "Authoring generation did not complete; no
  accepted proposal was persisted.", hiding even the fixed `ReviewError` text. One attempt; only an accepted
  verdict was kept (in the generated package).
- The 24-unit caps that matter were those of `AssessmentDraft`, `TeacherDraft`, `TrainerDraft` (units and items)
  and `StructuredTeacherDraft`; `DidacticDraft` (`aimpro/didactic.py`) serves only the earlier `generate-aimpro`
  command, which the studio does not use. A project holds one artifact per role (`slot = data.role.lower()`).
- "Binding proposals" of the roadmap: `propose-aimpro-bindings` belongs to the earlier `generate-aimpro` path; on
  the project path, resource bindings are part of the delivery import (S10).

## Owner decisions taken in this chat (10–11 November 2026)

Asked before the issue was opened; recorded in issue #110.

1. **The 24-unit caps: raise them to match the syllabus (96).** Materials to 288 (3 × 96), "if the model then
   manages them without problems" — not measured here (finding 1).
2. **D30 applies to the Evaluator, Teacher and Trainer reviews in this step.**
3. **S09c is split, core first.** This chat: the caps and D30 for the generators. Next: **S09c2**, the studio
   forms for the three generators (with the exact refs, a stale base refused at queue time and reloaded), a
   teacher view for every proposal kind of the seed, and the completion rules proposed from the studio (a
   server-side command with the fixed "every child completed" rule). Binding proposals move to S10.
4. **D28 and D29 are not needed** by S09c; teacher edits of generated content are out of scope.
5. Wait for PR #109 before branching.

Defaults taken without a question, stated here and in the guide:

- As for the Curator: the retry receives only the last draft (`rejected_draft`, the model's own output, the
  original components for a structured Teacher) and its feedback; the review agent never sees an earlier verdict.
- A draft that is not the typed contract (a `ValidationError` of the dispatcher or of a recorded text), a
  context over the budget and a review that is not a verdict stop at once. Unlike the Curator's loop, the drafts
  judged before such a stop are kept (`NotAccepted` with the stopping fixed text).
- A recorded Teacher response (`--recorded`, CLI only) is the first draft; a retry asks the model.
- The failure text is the last refusal's fixed text, now shown: "Authoring generation did not complete
  (Authoring output did not pass separate Lead review); no accepted proposal was persisted."
- Items per unit follow the units (96), as agreed; the caps are tied to the syllabus constant
  (`aimpro.syllabus.UNITS`, `aimpro.teacher_contracts.MATERIALS = 3 * UNITS`).
- API version 0.9.0 (one route added).

## Changes

| File | Content |
| --- | --- |
| `aimpro/syllabus.py` | `UNITS = 96`, the syllabus cap, now a constant |
| `aimpro/teacher_contracts.py` | `MATERIALS = 3 * UNITS`; `StructuredTeacherDraft` units, items, explanations, comparisons, peers, transcripts → `UNITS` |
| `aimpro/generators.py` | `ATTEMPTS = 3`; units and items → `UNITS`, materials → `MATERIALS`; `GenerationAttempt`, `Generated`, `GenerationResult` (a `LearningResponse` with `attempts`, omitted when empty), `NotAccepted`; `generate` loops (first prompt byte-identical to before), `PROJECT_AUTHORING_RETRY`, one content-free `review` event per draft; `_review` and `_typed_verdict` split from `checked_verdict` |
| `learning/generation.py` | records `GenerationResult` for a proposal and a failure, replays it; the failure shows the `ReviewError` text; `generation_request` and `OPERATIONS` |
| `learning/service.py` | `project_generation_request` |
| `services/authoring_api/projects.py`, `app.py` | `GET /contexts/{context_id}/generation-reviews/{request_id}` → `GenerationReviews`; version 0.9.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | regenerated |
| `apps/studio/src/features/course-build/ReviewAttempts.tsx`, `JobsList.tsx`, `buildApi.ts`, `i18n/en.json` | the job list offers "How the review agent judged the drafts of this job" for generator jobs; the four checks in words; labels and data only, no styling |
| `tests/generator_fixtures.py` | `GENERATION_REJECTION`; `SyntheticModels(*verdicts)`, a queue; `REJECT_ONCE` in a review prompt refuses it once (dev only); prompts and review prompts recorded |
| `tests/authoring_cycle_fixtures.py` | `SimulatedAuthoring.curator(units=1)`: a syllabus of several units on one target |
| `tests/test_authoring_generators.py`, `tests/test_structured_teacher.py`, `tests/services/test_job_worker.py`, `test_authoring_jobs_api.py`, `test_api_openapi.py` | contract tests (below); tests that counted one generator call before a check refusal now expect `ATTEMPTS`; the event stream of an Evaluator job has one `review` progress event |
| `apps/studio/test/build.test.tsx`, `apps/e2e/generation.spec.ts` (new), `apps/e2e/support.ts` | unit and browser tests |
| `docs/architecture/role-applications.md` | "Evaluator, Teacher and Trainer drafts (S09c)", the route, the browser test row |

## Verification

**Contract tests first.** The core and structured Teacher tests were written before the implementation and
failed to import (`ATTEMPTS`); the worker and API tests failed (5 failures: the two worker tests, the two API
tests and the OpenAPI route list) until the implementation and the regenerated snapshot. The 48-unit test was
run against the old caps (24 units, 96 materials, restored afterwards) and failed for all three roles. The
studio tests were written after the component.

| Check | Result |
| --- | --- |
| `unittest discover -q`, telemetry off, final tree | 1063 tests, OK, 195 skipped (1052 / 194 before: 11 new tests; the new skip is the PostgreSQL variant of the new worker test) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 136 tests OK (134 before) |
| `npx playwright test -c e2e/playwright.config.ts --list` | 13 tests in 7 files; compiles (typecheck includes `e2e/`) |
| `git diff --check` | exit 0 |

**Not verified locally.** The browser tests: running the browser stack was not permitted in this session; the
CI job `browser` ran them (below).

## Findings (not changed in this PR)

1. **Whether a live model writes a 96-unit draft is not measured.** The contracts now allow it, and a 48-unit
   synthetic syllabus reaches the three proposals; one model response for 48 units of assessments or Teacher
   materials (up to 144 materials) may exceed the provider's output limit or the context budget, and its review
   receives the whole draft. The owner wants to try it as soon as possible: a live run on LPO AI needs the
   owner's authorization and a number of runs.
2. **The generator review prompts are not calibrated.** Chat 20 calibrated the syllabus review on live verdicts;
   the project review prompt (`PROJECT_AUTHORING_REVIEW` and its Teacher and Trainer scopes) is unchanged. Now
   that its verdicts are kept, a measurement like Chat 20's is possible.
3. **An unparseable draft is not retried**, for the generators as for the Curator: a response that is not the
   typed contract stops the request at once with its type only.
4. **The retry prompt grows with the rejected draft.** For a large syllabus the retry carries the whole previous
   draft; only the structured Teacher checks its generation prompt against the budget, as before.
5. **Rejected drafts are not kept**, only their verdicts (D32 also applies here).
6. **Still open:** Chat 20 findings 1–2 (slow free model, abandonment noticed only at the end) now apply to
   generator jobs too.

## Open decisions

None blocked this step. Proposed for the owner to record in the roadmap (a chat does not edit it, working
protocol rule 9):

- the split of S09c into S09c (this PR) and S09c2 (studio forms, teacher views, completion rules), with S09c2's
  acceptance as agreed in this chat; binding proposals moved to S10;
- the decisions above (caps tied to the syllabus, D30 for the generators) as a D-row;
- a live measurement of the generators on a large syllabus and of their review (findings 1 and 2), with the
  owner's authorization.

Still open from the roadmap: D19, D21, D25, D28, D29, D31–D33, G7 / D4.

## Next step

**S09c2 — Studio forms, teacher views and completion rules.** Acceptance agreed with the owner in this chat:

- Browser test: from the studio the author queues the Evaluator, Teacher and Trainer jobs from their forms, reads
  each proposal in its teacher view, approves and applies it, then proposes and applies the completion rules; the
  project state (selected artifacts, no stale dependency, a rule on every node) is that of `build_project()` in
  `tests/test_authoring_cycle.py`, also checked by an API test.
- Each form shows the exact refs it sends; a stale base is refused (409) and the form reloads.
- Every proposal kind of the seed has a teacher view in words (browser test on each, and axe).

## PR and CI

PR and CI: see below.
