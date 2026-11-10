# Chat 20 handoff — the syllabus review made visible, retried and calibrated

Date: 10 November 2026. Base: `main` at `f1236e6` (PR #106 merged on top of PR #105, S09b).
Step: inserted between **S09b** and **S09c** of the [prototype roadmap](../prototype-roadmap.md); it has no
step id of its own.
Issue: [#107](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/107).
Branch `fix/s09b-review-transparency`, PR: see the end of this file.

No ALM metamodel, ALM store schema, jobs store schema, realm file, identity map or AIM-PRO/jjodel export
changed. The configured models were not changed. The owner's demo stack (ports 58000/58001, `/tmp/alm-demo`)
was not stopped or written: its stores were only read, and copied with SQLite's backup from a read-only
connection.

## Objective

The owner observed on 10 November 2026 (context `demo-s09b`, real worker,
`nvidia/nemotron-3.5-super-vl:free` for the Curator and the `lead` reviewer, Langfuse off) that the semantic
review rejected most Curator attempts and that the teacher could not tell why. Make the review visible,
measure it, and change only what the evidence supports.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| PR #105 (S09b), PR #106 (roadmap) | merged 10 November 2026, 13:06 and 13:24 UTC; `main` at `f1236e6` |
| `unittest discover`, telemetry off | 1034 tests, OK, 192 skipped (as Chat 19) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 132 tests OK (as Chat 19) |

The working tree had someone else's changes as before (`README.md` and the untracked
`docs/architecture/system-overview.md`, `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`,
`examples/lpo-ai/`); they are not part of this PR.

**What the demo jobs store held** (read-only, `/tmp/alm-demo/jobs.sqlite`, progress events):

| Job | Kind | Model calls | Outcome |
| --- | --- | --- | --- |
| #16 | Curator on prepared sources | Curator only (115 s) | FAILED, text hidden ("Selected-source authoring did not complete") |
| #17 | Curator on prepared sources | Curator, reviewer | FAILED, text hidden |
| #21 | Curator by a query | Curator, reviewer | FAILED: did not pass semantic review |
| #23, #25 | revisions | Curator, reviewer | FAILED: did not pass semantic review |
| #24 | Curator on prepared sources | Curator, reviewer | PROPOSED |
| #28 | Curator on prepared sources | none (0.6 s) | FAILED, text hidden |

Two causes were found besides the review itself: `_failed` hid the `ReviewError` text on the prepared-sources
path, and the coverage checks of a draft (`check_unit_coverage`) raised a plain `ValueError`, so their fixed
text was hidden on every path. Which check stopped #16 and why #28 failed before any model are **not known**;
both would now show a `ReviewError` text, and other errors still show only their type.

## Owner decisions taken in this chat (10 November 2026)

Asked before the issue was opened; recorded in issue #107.

1. Keep the review agent's verdict of every attempt **with the request's result in the ALM requests store**,
   read through the API and shown in the studio, labelled as model text.
2. The review of a revision receives the revision context (previous syllabus, the chain of reasons) as
   untrusted data.
3. A bounded Curator–reviewer loop inside one job: **at most 3 drafts**. A draft refused by the deterministic
   checks also counts as an attempt; the Curator receives the fixed check text.
4. When the drafts run out, **the job fails as before**, with the verdicts kept; a generated syllabus always
   carries an `ACCEPT` review.
5. Calibration on evidence: **4 live jobs before and 4 after** a prompt change, on copies of the demo stores
   with a separate process; the three clauses of the change were approved by the owner after the first four
   (below).
6. The prepared-sources path reports the fixed `ReviewError` text.
7. The configured models are not changed.

Defaults taken without a question, stated here and in the guide:

- The Curator's retry receives only the **last** draft and its feedback (`rejected_syllabus`,
  `review_feedback`), not the whole history. The review agent never sees an earlier verdict: each draft is
  judged on its own.
- A review over the budget or a review that is not a verdict stops at once (another draft would not change it).
- `SyllabusVerdict` is unchanged (no flag for "the revision does what was asked"): the review agent folds it
  into the verdict and its reason.
- The failure text is the last attempt's fixed text, as before ("Syllabus did not pass semantic review", or
  the check text).

## Changes

| File | Content |
| --- | --- |
| `aimpro/syllabus.py` | `ATTEMPTS = 3`; `SyllabusAttempt` (attempt, `review` or `check`); `generate` loops and returns `Reviewed(draft, verdict, attempts)`, or raises `NotAccepted` (a `ReviewError` carrying the attempts, never in its message); `AIMPRO_SYLLABUS_RETRY` and its data; one content-free `review` event per attempt; `_review` with `AIMPRO_SYLLABUS_REVISION_REVIEW`, `previous_syllabus`, `teacher_reasons` for a revision; three calibrated clauses (below) |
| `aimpro/syllabus_coverage.py` | `check_unit_coverage` raises `ReviewError` (same fixed texts) |
| `aimpro/syllabus_state.py` | `SyllabusResult`: a `LearningResponse` with `attempts`, omitted when empty |
| `aimpro/syllabus_service.py`, `aimpro/syllabus_refinement.py`, `aimpro/source_service.py` | the three paths record `SyllabusResult` for a proposal and a failure, and replay it; `_failed` adds the `ReviewError` text; `syllabus_request` reads a subject's ended syllabus request |
| `learning/service.py` | `aimpro_syllabus_request` |
| `services/authoring_api/syllabus.py`, `app.py` | `GET /contexts/{context_id}/syllabus-reviews/{request_id}` → `SyllabusReviews`; API version 0.8.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | regenerated |
| `apps/studio/src/features/course-build/ReviewAttempts.tsx` (new), `JobsList.tsx`, `buildApi.ts`, `review/RevisionStep.tsx`, `i18n/en.json` | "How the review agent judged the Curator's drafts", read when opened; labels and data only, no styling |
| `tests/syllabus_fixtures.py` | `verdict()`, `REJECTION`; `Reviewer(*first)` (a queue of verdicts); `Curator(retry=)`; `REJECT_ONCE`, a marker in a teacher's reason that makes the synthetic reviewer reject each review prompt once (dev only: synthetic worker and browser test) |
| `tests/test_aimpro_syllabus.py`, `test_syllabus_refinement.py`, `test_source_selection.py`, `test_syllabus_coverage.py`, `tests/services/test_job_worker.py`, `test_authoring_syllabus_api.py`, `test_api_openapi.py` | contract tests (below); coverage tests now expect `ATTEMPTS` Curator calls |
| `apps/studio/test/build.test.tsx`, `syllabus.test.tsx`, `apps/e2e/refinement.spec.ts` | unit, page and browser tests |
| `docs/architecture/role-applications.md` | "The review agent's assessment of each draft (Chat 20)", the route, the browser test row |

## Verification

**Contract tests first.** The core, service, worker and API tests were written before the implementation and
failed: 5 failures and 3 errors (`tests.test_aimpro_syllabus` could not import `ATTEMPTS`); the OpenAPI route
list was extended before the route existed and failed (7 failures) until the snapshot was regenerated. The
studio tests were written after the component.

| Check | Result |
| --- | --- |
| `unittest discover`, telemetry off, final tree | 1052 tests, OK, 194 skipped (1034 / 192 before; the 2 new skips are the PostgreSQL variants of the worker tests) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 134 tests OK (132 before) |
| `npx playwright test -c e2e/playwright.config.ts --list` | 12 tests in 6 files; compiles |
| `git diff --check` | exit 0 |

**Not verified locally.** The browser tests: ports 58000 and 58001 were held by the owner's demo stack, which
this chat did not stop; the CI job `browser` ran them (below).

## Live calibration (owner-authorized, 4 + 4 jobs)

Setup: `/tmp/alm-demo/alm.sqlite` copied with `sqlite3 "file:…?mode=ro" ".backup …"` into the chat's scratchpad;
each job ran the CLI (`python -m learning … generate-aimpro-syllabus --prepared-sources` or
`revise-aimpro-syllabus`) on its own copy, subject `admin`, context `demo-s09b`, policy
`course-demo-s09b-1.json`, with `LANGFUSE_ENABLED=false` and the configured `openrouter` profile
(`nvidia/nemotron-3.5-super-vl:free` for the Curator and the reviewer). Jobs: G1, G2 = generation on the
accepted preparation `9bfbb291-…` (export `e2d842b6…`); R1 = revision of `proposal-d8aa0d0a…` (built by a
query); R2 = revision of `proposal-3bb333dc…` (built on prepared sources); both proposals carry the request
"Add a unit where participants explain two choices". "Before" is this PR's code without the three clauses
(loop and revision context already in place).

Each reason not leading to ACCEPT was classified as **justified** (it names a real defect of the draft against
the rules) or **over-strict** (it rests on a ground the rules do not make a reason to reject), by its deciding
grounds.

### Before

| Job | Outcome | Time | Attempts | Classification |
| --- | --- | --- | --- | --- |
| G1 | FAILED | 847 s | REJECT, REJECT (`source_alignment` false), UNCERTAIN | #1 justified (claims about an SME adviser demonstration rest on an excerpt about AI agents for Academic English), with an over-strict secondary ground: retrieved excerpts that no unit cites; #2 over-strict: the unresolved source diagnostics and `conforms_to_generated_contracts=false` taken as deciding; #3 over-strict: the source diagnostics again, and claims the draft itself limits to a general principle treated as unsupported |
| G2 | PROPOSED | 194 s | ACCEPT | — |
| R1 | PROPOSED | 913 s | UNCERTAIN, REJECT, ACCEPT | #1 justified (a phrase of the scenario presented as the excerpt's; analogical use); #2 justified ("directly supports … routine business messages" beyond the excerpts, contradicting the draft's own gap); #3 accepted after the Curator narrowed its claims |
| R2 | PROPOSED | 363 s | ACCEPT | — (its reason checks that the revision adds the requested unit) |

Totals: 9 reviews, 3 ACCEPT; of the 6 others, 3 justified and 2 over-strict, plus one over-strict secondary
ground. 3 of 4 jobs proposed; without the loop R1 would have failed.

**Clauses changed** (approved by the owner), each tied to an observed over-strict ground; nothing else in the
review or Curator prompts changed:

1. "Source diagnostics and a source that does not conform to the generated contracts describe the external
   model, not the draft: name them as unresolved, but they are not by themselves grounds for REJECT,
   UNCERTAIN or a false source_alignment." (G1 #2, #3)
2. "unsupported claims or irrelevant retrieval require REJECT or UNCERTAIN" became "unsupported claims, or
   claims resting on irrelevant excerpts, require REJECT or UNCERTAIN; retrieved excerpts that no unit cites are
   not grounds for rejection." (G1 #1)
3. "Judge each supported_claim as worded: a claim limited to what its excerpt states, such as a general
   principle whose transfer to this audience the draft declares as a gap, is supported; a claim that goes
   beyond its excerpt is not." (G1 #3; R1 #3 accepted such claims)

### After

| Job | Outcome | Time | Attempts |
| --- | --- | --- | --- |
| G1 | PROPOSED | 252 s | ACCEPT |
| G2 | PROPOSED | 398 s | ACCEPT |
| R1 | PROPOSED | 327 s | ACCEPT |
| R2 | PROPOSED | 264 s | ACCEPT (its reason checks that the revision adds the requested unit and leaves units 01–02 unchanged) |

Totals: 4 reviews, 4 ACCEPT; 4 of 4 jobs proposed, each with one draft. Three of the four reasons name the new
clauses explicitly (uncited excerpts, source diagnostics, claims judged as worded).

| | Jobs proposed | Reviews | ACCEPT | Justified refusals | Over-strict refusals |
| --- | --- | --- | --- | --- | --- |
| Before | 3 / 4 | 9 | 3 | 3 | 2 (+1 secondary ground) |
| After | 4 / 4 | 4 | 4 | 0 | 0 |

**Spot check of an acceptance** (G1 after, the job that failed before): every `supported_claim` restates what its
excerpt says (for example "oDSP-HF … applied to AI agents supporting Academic English writing and computational
thinking"), and the draft's gaps declare that the oDSP-HF and AI Maturity Matrix evidence does not validate
transfer to micro-business owners and that the teacher's limitations were uninformative. That is supported "as
worded" under clause 3. **Caveats:** four jobs per phase cannot separate the clauses from the model's variance
(G2 and R2 were accepted at once before the change too); and an excerpt that is true but only loosely relevant
to a unit now passes when the draft declares the transfer as a gap, so its relevance is left to the teacher,
who reads the gaps and the excerpts in the syllabus view (finding 5).

## Findings (not changed in this PR)

1. **The free model is slow and verbose.** A review takes 1.5–3.5 minutes and 8–17k output tokens; a job of
   three drafts can take about 15–20 minutes. The studio follows the job meanwhile; nothing times it out.
2. **Abandonment is noticed only at the end.** An administrator who abandons a running job does not stop the
   loop: the remaining drafts are made, and the final write is refused as before.
3. **Rejected drafts are not kept**, only their verdicts. The teacher reads why a draft was refused but not the
   draft itself; keeping drafts would add up to three syllabi per request.
4. **Other failures still hide their cause by design** (type only in the log): job #28 failed before any model
   for a reason this chat could not determine from the stores.
5. **The prepared excerpts drive most refusals, and now the teacher judges their relevance.** In G1 the
   teacher's preparation selected an excerpt about AI agents for Academic English ("Scaffolding", limitation
   "nof found"); before the change the review agent refused SME-specific claims on it (rightly); after it, the
   Curator restated what the excerpt says and declared the transfer as a gap, and the review agent accepted.
   Whether such a loosely relevant citation should block a syllabus is an owner decision; today the gap is
   shown to the teacher, who decides.
6. **Whether another `lead` model changes the picture is not measured**: the models were not changed (owner
   decision 7). The reviewer's reasons here are long, repeat the source diagnostics in every verdict and are
   mostly consistent with the rules; a stronger model may need fewer attempts.
7. **A synthetic test marker in teacher text** (`REJECT_ONCE`) exists only in the dev fixtures; the production
   reviewer never sees it unless a teacher types it.
8. **Still open:** the 24-unit caps (S09c); Chat 19 findings 1–8.

## Open decisions

None blocked this chat. Proposed for the owner to record in the roadmap (a chat does not edit it, working
protocol rule 9):

- the decisions above, as a D-row for the review of a Curator syllabus (attempts, kept verdicts, revision
  context, calibrated clauses);
- whether to keep rejected drafts (finding 3), and whether abandonment should stop the loop between drafts
  (finding 2);
- a measurement with another `lead` model (finding 6), with the owner's authorization.

Still open from the roadmap: D19, D21, D25, D28, D29, G7 / D4.

## Next step

After the owner merges this PR (which closes #107): **S09c — Rubrics, assessments and content from the
studio**, whose acceptance is in the roadmap; it includes the 24-unit caps, with the owner.

## PR and CI

PR_SECTION
