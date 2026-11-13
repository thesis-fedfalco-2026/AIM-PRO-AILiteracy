# Chat 23 handoff — S09d: generation by blocks of units

Date: 12 November 2026. Base: `main` at `4e70e75` (PR #117 merged).
Step: **S09d**, a new step the owner placed before S09c2 part 2 (the roadmap does not list it yet; proposed below).
Issue: [#118](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/118).
Branch `feat/s09d-generation-blocks`, PR: see the end of this file.

No ALM metamodel, ALM store schema, jobs store schema, realm file, identity map, configured model,
`runtime.properties` or AIM-PRO/jjodel export changed. No model was called before the PR. The owner's demo stack
(58000/58001, `/tmp/alm-demo`) was running and was not touched, so the browser tests were not run locally (they
run in CI).

## Objective

The Evaluator, Teacher and Trainer write a large syllabus in several model responses (blocks of units) instead of
one, so that a 48-unit course can get its assessments and content with the configured model.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git status` | `main`; someone else's changes as before (`README.md`, untracked `docs/architecture/system-overview.md`, `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/`), not part of this PR |
| `git log --oneline -3` (`main` = `origin/main`) | `4e70e75` merge of #117, `0d61924`, `b1a7508`: as the Chat 22 handoff |
| `gh pr list --state open` | none |
| `unittest discover -q`, telemetry off | 1081 tests, OK, 200 skipped (as Chat 22) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 146 tests OK (as Chat 22) |

**What was found** (read before asking the owner):

- `GenerationInput` has one digest and `checked_draft` requires a draft to cover every target unit in order, so a
  block needs its own input (a subset of the target units, with its own digest) and an assembly step that yields
  the one draft `revision()` takes.
- `GeneratedArtifact.review` holds one verdict: a proposal assembled from blocks reviewed one by one needs either a
  new artifact format or a final review of the assembled draft.
- Each block request still carries the full input (approved syllabus, sources and, for the Teacher and Trainer, the
  approved assessments): blocks shorten the output, which reached the deadline, not the input.
- The structured Teacher's `teacher_plan` (transcript-peer links, protected case facts) is not tied to units.
- The deadline interceptor raised an `httpx.ReadTimeout`; not being a `ReviewError`, the job showed the generic
  text. CrewAI re-raises provider errors with `raise … from e` or a bare `raise`, so the cause chain survives.
- `LearningService` (Socratic continuity) and `releases._recorded` read every request of a context and skip rows
  whose payload is not theirs, so accepted blocks can be kept as request records without a schema change.

## Owner decisions taken in this chat (12 November 2026)

Asked before the issue was opened; recorded in issue #118.

1. **Block size**: fixed, 12 target units per block.
2. **Review under D30**: each block is judged by the review agent on its own (up to three drafts per block), and
   the assembled draft is judged once at the end.
3. **A block whose drafts run out** fails the job; the accepted blocks are kept and a new job with the same command
   on the same exact inputs reuses them without a model call.
4. **One proposal per job**, assembled from all blocks.
5. **Scope**: Evaluator, Teacher (unstructured) and Trainer; the structured Teacher and the Curator keep one
   response.
6. **A final review that is not `ACCEPT`** fails the job, the accepted blocks kept, no automatic regeneration.
7. **Failure detail and progress**: a fixed text names a model call past its deadline; content-free block events,
   shown in the studio job list.
8. **What the agents see**: the review of a block sees the full input and that block only; the generator of block N
   sees the full input, its units and the accepted drafts of blocks 1..N-1.
9. **A syllabus of at most 12 target units** is one block, and its assembled draft is still judged.
10. **Live measurement**: one Evaluator job on a copy of `antonio-lpo` after CI, CLI, Langfuse off, at most 25 model
    calls, stopping at the first failure.
11. Step id **S09d**, one PR.

Defaults taken without a question, stated here and in the guide:

- Accepted blocks are request records of the ALM requests store (`generation-block:<sha256>`, operation
  `PROJECT_GENERATE_BLOCK`), keyed by the block's input digest, the subject and the drafts of the blocks before it.
  A reused block is checked again before use; one that no longer passes is written again.
- A block's material keys must not repeat an earlier block's: a fixed check, retried like any other.
- The timeout text also applies to the structured Teacher (the common path of `generate`); the Curator is unchanged.
- The synthetic reviewer's `REJECT_ONCE` marker (dev only) refuses the review of a block once, never the review of
  the assembled draft.
- API version 0.11.0 (`JobView.blocks`; `GenerationAttempt` gains `block`, `final`, `reused`).

## Changes

| File | Content |
| --- | --- |
| `aimpro/generators.py` | `BLOCK_UNITS`, `TIMED_OUT`, `UnitBlock`; `GenerationInput.block` (omitted when unset) restricts `target_units`; `GenerationAttempt.block`, `final`, `reused` (omitted when unset); `generate` takes `kept`, writes unstructured requests by blocks (`_blocks`: `PROJECT_AUTHORING_BLOCK`, `previous_blocks`, `_across_blocks`, assembly, final review), keeps the structured Teacher in one response (`_drafts`, the former loop); `PROJECT_AUTHORING_BLOCK_REVIEW`; a call past its deadline fails with `TIMED_OUT` |
| `agent_system/deadline.py` | `DeadlineExceeded`, `expired`, `reached` (the cause chain) |
| `agent_system/events.py` | event type `block` |
| `learning/generation.py` | `KeptBlocks`; `generate_project` passes it |
| `services/authoring_api/jobs.py`, `app.py` | `BlockProgress`, `JobView.blocks`; version 0.11.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | regenerated |
| `apps/studio/src/features/course-build/JobsList.tsx`, `ReviewAttempts.tsx`, `i18n/en.json` | "Blocks of units written: 2 of 4"; each draft's block, a reused block, the assembled draft (labels and data only) |
| `tests/test_generation_blocks.py` (new), `tests/services/test_authoring_jobs_api.py` | contract tests (below) |
| `tests/generator_fixtures.py` | `whole()`; `REJECT_ONCE` refuses a block review only |
| `tests/test_authoring_generators.py`, `tests/test_structured_teacher.py`, `tests/services/test_job_worker.py`, `tests/services/test_authoring_jobs_api.py` | tests that counted model calls or attempts now expect the final review; tests that read a model's input use `whole()` |
| `apps/studio/test/build.test.tsx`, `apps/e2e/generation.spec.ts` | studio unit test; the browser test reads the block labels |
| `docs/architecture/role-applications.md`, `docs/architecture/event-log.md` | "Generation by blocks of units (S09d)"; the `block` event and the generator `review` stages |

## Verification

**Contract tests first.** `tests/test_generation_blocks.py` was written before the implementation and failed to
import (`BLOCK_UNITS`, `TIMED_OUT`, `expired`); the job view test
(`test_a_job_shows_how_many_of_its_blocks_are_written`) failed (no `blocks`) until `JobView.blocks`. The existing
tests that broke were updated after the implementation (each listed above). The studio tests were written after the
components.

| Check | Result |
| --- | --- |
| `unittest discover -q`, telemetry off, final tree | 1092 tests, OK, 200 skipped (1081 / 200 before: 11 new tests, 10 in `test_generation_blocks.py` and 1 job view test) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 147 tests OK (146 before) |
| `npx playwright test -c e2e/playwright.config.ts --list` | 15 tests in 8 files; compiles (typecheck includes `e2e/`) |
| `git diff --check` | exit 0 |

**Not verified locally.** The browser tests: the owner's demo stack held their ports; the CI job `browser` runs
them (below).

## Findings (not changed in this PR)

1. **The final review still reads the whole draft.** For 48 units its input is about as large as a Curator review
   (190–220k input tokens in the Chat 21 trial) and its output small; whether it fits the deadline is measured by the
   live run below.
2. **Input grows with the blocks.** Each block carries the full input, and block N the drafts of blocks 1..N-1; a
   48-unit Evaluator job makes at least 9 model calls (4 drafts, 4 block reviews, 1 final review) instead of 2.
3. **A small syllabus pays one more review** (owner decision 9), and its generation prompt carries the block clause.
4. **Kept blocks are never removed.** They are model drafts in the requests store of the context, like failed
   requests; no retention rule exists.
5. **Abandonment is still noticed only at the end** (D32): the loop does not check between blocks.
6. **The structured Teacher and the Curator keep one response**; a 48-unit structured Teacher may reach the deadline,
   and a Curator call past it still fails with the generic text.
7. **Still open:** Chat 21 findings (generator review prompts not calibrated; unparseable drafts not retried; retry
   prompt grows; rejected drafts not kept) and Chat 21/22 trial findings.

## Open decisions

Proposed for the owner to record in the roadmap (a chat does not edit it, working protocol rule 9), with the
proposals of the Chat 22 handoff:

- a step **S09d — Generation by blocks of units** after S09c2 part 1 and before S09c2 part 2, goal "a 48-unit course
  gets its assessments and content with the configured model", acceptance as issue #118;
- a D-row for this chat: blocks of 12 target units for the Evaluator, Teacher and Trainer; each block reviewed under
  D30 with the full input and that block only, the assembled draft reviewed once; a failed block or final review
  fails the job and keeps the accepted blocks, reused over the same exact inputs; one proposal per job; structured
  Teacher and Curator unchanged; a fixed text for a call past its deadline.

Still open from the roadmap: D19, D21, D25, D28, D29, D31–D33, G7 / D4.

## Next step

**S09c2 part 2** (unchanged, from issue #115): a read route for one proposal with its candidates, whatever its
status; a teacher view in words for project initialization, release and delivery import, and for proposals that are
no longer pending, with a browser test on each seeded proposal kind and axe.

## PR and CI

PR [#119](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/119), commit `e631bee` (the change and
this handoff), then this record. CI on `e631bee`, push run
[43184892421](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/43184892421) and pull_request
run [43184901818](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/43184901818): all 7 jobs of
each passed, `browser` included (`generation.spec.ts`: "Blocks of units written: 1 of 1", block 1 refused once, then
accepted, the assembled draft accepted) and `store-backends`.

## Live measurement on antonio-lpo (after CI)

**Authorization** (owner, 12 November 2026, decision 10): one Evaluator job on a copy of `antonio-lpo`, CLI,
`LANGFUSE_ENABLED=false`, the configured model, at most 25 model calls, stopping at the first failure. Setup:
`/tmp/alm-demo/alm.sqlite` copied with `sqlite3 "file:…?mode=ro" ".backup …"` into the chat's scratchpad, with the
policy `course-antonio-lpo-1.json`; context at `fac0368087f649219194faaf6130041e` (the state of the Chat 22 trial:
project `main` applied, syllabus of 48 units, no requirement), subject `admin`, the configured `openrouter` profile
(`nvidia/nemotron-3.5-super-vl:free`). The CLI ran through a wrapper that bound a content-free JSONL event log (the
CLI has none). A first start failed at import (the wrapper was outside the repository and the repository was not
on `PYTHONPATH`) before any request was reserved or model called; it is not counted. The demo stack was not
touched.

| Request | What happened | Model calls |
| --- | --- | --- |
| `live-evaluator-blocks-1`, 48 units = 4 blocks of 12 | **FAILURE after 872 s** (08:53:55–09:08:27 UTC) at block 1: draft 1 refused by the checks after 195 s ("Output must preserve exact syllabus unit coverage and ordering"), draft 2 after 267 s ("Citation is outside the exact supplied source/version/excerpts"), draft 3 after 410 s (coverage and ordering again); no draft reached the review agent; no block kept; the course copy unchanged | 3 (`assessment-designer`) |

The job stopped at the first failure as agreed; 3 of 25 calls were used. The job detail is the fixed text of the last
check; the three attempts carry `block: 1`; the events were three `review` (`PROJECT_CHECKS`, block 1) and one
`block` (`NOT_ACCEPTED`). Token counts were not measured: the CLI does not record `provider.call` events.

**What it shows.** Each block response fitted the 600 s deadline (195–410 s for 12 units, where one response for 48
units had not finished in 600 s), so blocks remove the timeout of the trial. The drafts then failed the deterministic
checks: two did not cover exactly the 12 units of the block in order, one cited an excerpt outside the supplied
ones. Why is not known: the refused drafts are not kept (D32), and the check text names no unit, so the retry could
not tell the model which units were wrong. A likely cause, not verified: the request carries the whole syllabus
(`input.units`, 48 units) beside the 12 `target_units`.

### Findings of the measurement (not changed)

1. **The coverage check does not say which units are missing, extra or out of order**, for the generators as it did
   for the Curator before issue #112 (where the citation check now names the units). A retry receives only the fixed
   text. Naming the expected host unit keys (never the model's own keys) in the check is a possible change; an owner
   decision.
2. **The generator sees every unit of the syllabus.** Restricting `input` to the block's units, or saying more
   plainly that only `target_units` are written, would change the prompt; an owner decision, measured live before
   it is relied on.
3. **The citation check of the generators does not name the offending items or excerpts**, and the generators do
   not receive the citable excerpts as the Curator does since issue #112.
4. **Token use of a block is not measured**: the CLI binds no provider event listener.

### Owner decisions after the measurement (13 November 2026)

1. **Finding 1: the coverage check names the units, in words the author can read**, since its text reaches the
   author (the job detail and "How the review agent judged the drafts of this job"). Done in this PR (below).
2. **Finding 2: the generator keeps receiving the whole syllabus.** No change.
3. **The roadmap records S09d and its D-row**, in a separate documentation PR (below).

Change, contract tests first (`test_missing_and_unrequested_units_are_named_by_syllabus_position_and_their_keys_fed_back`
and `test_repeated_and_reordered_units_are_refused_in_words` failed with the former text until the change):
`aimpro.generators._coverage` raises `CheckRefusal` (`aimpro.syllabus`, as the Curator's citation check since issue
#112) with "The draft must cover each unit it was asked to write once, in the order of the syllabus: …" and the
missing units by their position in the syllabus, the count of units it was not asked to write, of units written
more than once, or "its units are not in the order of the syllabus"; never the draft's own keys. The retry receives
`check_details` (`expected_unit_keys`, `missing_unit_keys`, `unexpected_unit_keys`) as data, and
`PROJECT_AUTHORING_RETRY` says so. Findings 3 (the citation check names no item) and 4 stay open. Whether the change
makes a 48-unit Evaluator job pass is measured below (the owner asked to try again, 13 November 2026).

| Check (coverage text) | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 1094 tests, OK, 200 skipped (1092 before: 2 new tests) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0 (no API schema change) |

## Second live measurement (13 November 2026)

**Authorization**: the owner asked to try again ("riprova", 13 November 2026), read as one more Evaluator job under
the terms of decision 10 (copy of `antonio-lpo`, CLI, `LANGFUSE_ENABLED=false`, at most 25 calls, stopping at the
first failure), after CI on `5e1ddf4` (push run 43408933164 and pull_request run 43408941408: every job passed).
A fresh read-only backup of `/tmp/alm-demo/alm.sqlite` (the context still at `fac0368087f649219194faaf6130041e`),
the same command and model.

| Request | What happened | Model calls |
| --- | --- | --- |
| `live-evaluator-blocks-2`, 48 units = 4 blocks of 12 | **FAILURE after 605 s** (10:38:26–10:48:31 UTC): the first `assessment-designer` call of block 1 reached the 600 s deadline while still writing; the job detail is "Authoring generation did not complete (A model call reached its time limit); no accepted proposal was persisted."; no attempt, no block kept, the course copy unchanged | 1 |

The fixed timeout text works as intended (the job detail and the warning log carry it, not the provider's message).
No content-free event was written: the call ended before any check or review. The coverage text of the change above
was therefore not exercised live.

### Finding of the second measurement (not changed)

5. **The free model's time for one block varies widely.** The same 12-unit block took 195, 267 and 410 s in the first
   measurement and over 600 s here. A block of 12 units does not reliably fit the deadline with
   `nvidia/nemotron-3.5-super-vl:free`. Options for the owner, none decided: smaller blocks (a change of D34), a
   longer `[llm] timeout` (`runtime.properties`, owner only), or another model (D33).
